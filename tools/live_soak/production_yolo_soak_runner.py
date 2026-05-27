#!/usr/bin/env python3
"""Production YOLO live soak runner for Phase 10.1b-5d.

Reads curated val images from the Phase 10 dataset, runs the production
ort_localizer.py on each image to obtain real YOLO bboxes/confidence/
defect_type, and uploads via POST /api/edge/report with full provenance.

Gates:
  A. Source category gate -- only metal_nut and cable from curated dataset.
  B. Production inference gate -- real YOLO output, no fabrication.
  C. Metadata gate -- anomaly_score from EfficientAD or documented default.
  D. Audit gate -- per-image validation table before upload.

Modes:
  --dry-run   Scan and validate only, no POST. Fails if any candidate invalid.
  --pre-soak  Upload 10-20 images, verify enrichment lifecycle.
  (default)   Dry-run then pre-soak.

Usage:
  export EDGE_UPLOAD_TOKEN=<your_token>
  python3 production_yolo_soak_runner.py \\
    --model <path/to/yolov8n.onnx> \\
    --classes <path/to/phase10_classes.yaml> \\
    --val-dir <path/to/datasets/phase10/images/val> \\
    --api <http://HOST:PORT> \\
    --mode dry-run|pre-soak|full \\
    --limit 10 \\
    --conf 0.25 \\
    --iou 0.45
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_CATEGORIES = {"metal_nut", "cable"}
LOCALIZATION_SOURCE = "ort_yolov8n_cpu"
LABEL_SOURCE = "yolo_class_head"
SCHEMA_VERSION = "v1"
VARIANT = "2B_base"

FORBIDDEN_KEYS = frozenset([
    "bbox", "bboxes", "mask", "category", "defect_type", "confidence",
    "anomaly_score", "geometry_correction", "localization_source", "label_source",
])

# Invalid defect ids from the failed 5d soak (must be excluded).
INVALID_DEFECT_IDS = set(range(4113, 4151))


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Production YOLO soak runner")
    p.add_argument("--model", required=True, help="Path to YOLOv8n ONNX model")
    p.add_argument("--classes", required=True, help="Path to phase10_classes.yaml")
    p.add_argument("--val-dir", required=True,
                   help="Path to val images directory (datasets/phase10/images/val)")
    p.add_argument("--api", required=True, help="Backend API base URL (http://HOST:PORT)")
    p.add_argument("--token-env", default="EDGE_UPLOAD_TOKEN",
                   help="Environment variable name for upload token (default: EDGE_UPLOAD_TOKEN)")
    p.add_argument("--token", default=None,
                   help="Upload token directly. DEPRECATED: prefer --token-env for operational safety. "
                        "If both --token and --token-env are set, --token takes precedence.")
    p.add_argument("--mode", choices=["dry-run", "pre-soak", "full"],
                   default="dry-run", help="Run mode (default: dry-run)")
    p.add_argument("--limit", type=int, default=20,
                   help="Max images for pre-soak mode (default: 20)")
    p.add_argument("--conf", type=float, default=0.25, help="YOLO confidence threshold")
    p.add_argument("--iou", type=float, default=0.45, help="NMS IoU threshold")
    p.add_argument("--img-size", type=int, default=640, help="YOLO input image size")
    p.add_argument("--anomaly-score", type=float, default=0.0,
                   help="anomaly_score placeholder when EfficientAD not available. "
                        "Set to 0.0 and document as placeholder.")
    p.add_argument("--localizer-script",
                   default="scripts/phase10/ort_localizer.py",
                   help="Path to ort_localizer.py")
    p.add_argument("--timeout", type=int, default=30,
                   help="HTTP timeout for /api/edge/report (seconds)")
    p.add_argument("--enrich-timeout", type=int, default=90,
                   help="Max wait for enrichment completion (seconds)")
    p.add_argument("--output", default=None,
                   help="Path to save audit JSON (default: stdout only)")
    p.add_argument("--allow-ineligible", action="store_true",
                   help="In dry-run mode: exit 0 even if some candidates are "
                        "blocked. Default (strict) exits 1 if any blocked.")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Image discovery
# ---------------------------------------------------------------------------

def discover_val_images(val_dir: str) -> list[tuple[str, str]]:
    """Return [(image_path, source_category)] from curated val directory.

    Infers category from filename prefix: metal_nut_* or cable_*.
    Returns only images matching ALLOWED_CATEGORIES.
    """
    images = []
    for fname in sorted(os.listdir(val_dir)):
        fpath = os.path.join(val_dir, fname)
        if not os.path.isfile(fpath):
            continue
        if not fname.lower().endswith((".png", ".jpg", ".jpeg")):
            continue
        # Infer category from filename prefix.
        base = fname.lower()
        if base.startswith("metal_nut"):
            cat = "metal_nut"
        elif base.startswith("cable"):
            cat = "cable"
        else:
            continue  # Gate A: skip non-allowed categories.
        images.append((fpath, cat))
    return images


# ---------------------------------------------------------------------------
# YOLO inference via ort_localizer.py subprocess
# ---------------------------------------------------------------------------

class LocalizerSubprocess:
    """Manages a long-lived ort_localizer.py subprocess."""

    def __init__(self, localizer_script: str, model: str, classes: str,
                 conf: float, iou: float, img_size: int):
        self.script = localizer_script
        self.model = model
        self.classes = classes
        self.conf = conf
        self.iou = iou
        self.img_size = img_size
        self.proc: subprocess.Popen | None = None

    def start(self) -> None:
        cmd = [
            sys.executable, self.script,
            "--model", self.model,
            "--classes", self.classes,
            "--conf", str(self.conf),
            "--iou", str(self.iou),
            "--img-size", str(self.img_size),
        ]
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1,
        )
        # Read the ready signal.
        ready_line = self.proc.stdout.readline()
        if not ready_line:
            raise RuntimeError("ort_localizer.py failed to start")
        ready = json.loads(ready_line)
        if not ready.get("ready"):
            raise RuntimeError("ort_localizer.py not ready: %s" % ready)

    def infer(self, image_path: str) -> dict:
        """Send one image path, read one JSON result."""
        if not self.proc:
            raise RuntimeError("localizer not started")
        self.proc.stdin.write(image_path + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("localizer subprocess died")
        return json.loads(line)

    def close(self) -> None:
        if self.proc:
            try:
                self.proc.stdin.write("__EXIT__\n")
                self.proc.stdin.flush()
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()


# ---------------------------------------------------------------------------
# Validation gates
# ---------------------------------------------------------------------------

class GateResult:
    def __init__(self):
        self.will_upload = True
        self.reasons: list[str] = []

    def block(self, reason: str) -> None:
        self.will_upload = False
        self.reasons.append(reason)

    @property
    def reason_str(self) -> str:
        return "; ".join(self.reasons) if self.reasons else ""


def validate_detection(image_path: str, source_category: str,
                       yolo_result: dict, anomaly_score: float) -> tuple[GateResult, dict]:
    """Apply all validation gates. Returns (gate_result, upload_meta)."""
    gate = GateResult()
    fname = os.path.basename(image_path)

    # Gate B: YOLO must succeed.
    if not yolo_result.get("ok"):
        gate.block("yolo_failed: %s" % yolo_result.get("error", "unknown"))
        return gate, {}

    # Gate B: bboxes must not be empty.
    bboxes = yolo_result.get("bboxes", [])
    if not bboxes:
        gate.block("no_bboxes")

    # Gate B: confidence must be > 0.
    confidence = yolo_result.get("confidence", 0.0)
    if confidence <= 0:
        gate.block("confidence_zero")

    # Gate B: category from YOLO must match source category.
    yolo_category = yolo_result.get("category", "")
    if yolo_category != source_category:
        gate.block("category_mismatch: yolo=%s source=%s" % (yolo_category, source_category))

    # Gate B: defect_type must be non-empty.
    defect_type = yolo_result.get("defect_type", "")
    if not defect_type or defect_type == "anomaly":
        gate.block("defect_type_invalid: %s" % defect_type)

    # Gate A: source category must be allowed.
    if source_category not in ALLOWED_CATEGORIES:
        gate.block("category_not_allowed: %s" % source_category)

    # Build upload meta (always, even if blocked, for audit).
    # edge_ts and run_id are injected later at upload time for uniqueness.
    meta = {
        "line_id": "L1",
        "category": source_category,
        "defect_type": defect_type,
        "severity": "high" if confidence > 0.8 else "medium",
        "confidence": round(confidence, 4),
        "anomaly_score": round(anomaly_score, 2),
        "bboxes": bboxes,
        "description": "production_yolo_soak %s/%s" % (source_category, defect_type),
        "variant": VARIANT,
        "pipeline_ms": {
            "efficientad": 0.0,
            "fastsam": 0.0,
            "qwen3vl": 0.0,
        },
        "schema_version": SCHEMA_VERSION,
        "localization_source": LOCALIZATION_SOURCE,
        "label_source": LABEL_SOURCE,
    }

    return gate, meta


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def convert_to_jpeg(image_path: str) -> str:
    """Convert image to temporary JPEG file. Returns temp file path.

    The backend /api/edge/report accepts JPEG only. This function reads
    the source image (PNG or JPEG) and writes a temporary JPEG copy.
    Caller is responsible for cleaning up the temp file.
    """
    import cv2
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError("cannot read image: %s" % image_path)
    fd, tmp_path = tempfile.mkstemp(suffix=".jpg", prefix="soak_tmp_")
    os.close(fd)
    cv2.imwrite(tmp_path, img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return tmp_path


def upload_defect(api: str, token: str, meta: dict, image_path: str,
                  timeout: int) -> dict:
    """POST /api/edge/report with multipart form data.

    Converts image to JPEG before upload (backend accepts JPEG only).
    Temporary JPEG is cleaned up after upload.
    """
    tmp_jpeg = None
    try:
        ext = os.path.splitext(image_path)[1].lower()
        if ext in (".jpg", ".jpeg"):
            jpeg_path = image_path
        else:
            jpeg_path = convert_to_jpeg(image_path)
            tmp_jpeg = jpeg_path

        boundary = "----SoakRunner" + uuid.uuid4().hex[:12]
        meta_json = json.dumps(meta)
        with open(jpeg_path, "rb") as f:
            img_data = f.read()

        body = (
            ("--%s\r\nContent-Disposition: form-data; name=\"meta\"\r\n"
             "Content-Type: application/json\r\n\r\n%s\r\n" % (boundary, meta_json)).encode()
            + ("--%s\r\nContent-Disposition: form-data; name=\"image\"; "
               "filename=\"soak.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n" % boundary).encode()
            + img_data
            + ("\r\n--%s--\r\n" % boundary).encode()
        )

        req = urllib.request.Request(
            "%s/api/edge/report" % api,
            data=body, method="POST",
            headers={
                "Content-Type": "multipart/form-data; boundary=%s" % boundary,
                "Authorization": "Bearer %s" % token,
            },
        )
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode())
        result["_upload_latency"] = round(time.time() - t0, 3)
        return result
    finally:
        if tmp_jpeg and os.path.exists(tmp_jpeg):
            os.unlink(tmp_jpeg)


def check_enrichment(api: str, defect_id: int, timeout: int) -> dict | None:
    """Poll enrichment status until terminal state or timeout."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            url = "%s/api/defects/%d/enrichment" % (api, defect_id)
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                if data.get("status") in ("complete", "rejected", "failed"):
                    data["_enrich_latency"] = round(time.time() - t0, 3)
                    return data
        except Exception:
            pass
        time.sleep(2)
    return None


def check_canonical(api: str, defect_id: int) -> dict:
    """Fetch defect and verify canonical fields."""
    url = "%s/api/defects/%d" % (api, defect_id)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


# ---------------------------------------------------------------------------
# Audit table
# ---------------------------------------------------------------------------

AUDIT_HEADER = (
    "%-4s %-30s %-12s %-12s %-20s %-4s %-8s %-8s %-20s %-16s %-5s %s"
    % ("#", "image", "src_cat", "post_cat", "defect_type", "nbbox",
       "conf", "anom", "loc_source", "lbl_source", "upload", "reason")
)
AUDIT_SEP = "-" * 160


def print_audit_row(i: int, image_path: str, source_cat: str,
                    meta: dict, gate: GateResult) -> None:
    fname = os.path.basename(image_path)
    post_cat = meta.get("category", "-")
    dt = meta.get("defect_type", "-")
    nbbox = len(meta.get("bboxes", []))
    conf = meta.get("confidence", 0)
    anom = meta.get("anomaly_score", 0)
    loc = meta.get("localization_source", "-")
    lbl = meta.get("label_source", "-")
    upload = "YES" if gate.will_upload else "NO"
    reason = gate.reason_str
    print(AUDIT_HEADER[:0] +  # dummy to suppress lint
          "%-4d %-30s %-12s %-12s %-20s %-4d %-8.3f %-8.1f %-20s %-16s %-5s %s"
          % (i, fname, source_cat, post_cat, dt, nbbox, conf, anom,
             loc, lbl, upload, reason))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # Resolve token: --token overrides --token-env.
    if args.token:
        print("WARNING: --token is deprecated. Use --token-env or set the "
              "environment variable directly.", file=sys.stderr)
        token = args.token
    else:
        token = os.environ.get(args.token_env, "")
        if not token:
            print("ERROR: token not found. Set %s or use --token." % args.token_env,
                  file=sys.stderr)
            sys.exit(1)

    # Discover images.
    images = discover_val_images(args.val_dir)
    if not images:
        print("ERROR: no valid images found in %s" % args.val_dir)
        sys.exit(1)

    print("=== Production YOLO Soak Runner ===")
    print("  Mode: %s" % args.mode)
    print("  Val dir: %s" % args.val_dir)
    print("  Images found: %d (metal_nut + cable only)" % len(images))
    print("  Model: %s" % args.model)
    print("  Classes: %s" % args.classes)
    print("  Conf/IoU: %.2f/%.2f" % (args.conf, args.iou))
    print("  Anomaly score: %.1f (placeholder)" % args.anomaly_score)
    print()

    # Start localizer subprocess.
    localizer = LocalizerSubprocess(
        args.localizer_script, args.model, args.classes,
        args.conf, args.iou, args.img_size,
    )
    print("Starting ort_localizer.py subprocess...")
    localizer.start()
    print("Localizer ready.")
    print()

    # Run inference on all images.
    print(AUDIT_HEADER)
    print(AUDIT_SEP)

    audit_rows = []
    valid_candidates = []

    for i, (img_path, src_cat) in enumerate(images):
        yolo_result = localizer.infer(img_path)
        gate, meta = validate_detection(
            img_path, src_cat, yolo_result, args.anomaly_score)
        print_audit_row(i + 1, img_path, src_cat, meta, gate)

        row = {
            "i": i, "image": os.path.basename(img_path),
            "source_category": src_cat,
            "yolo_ok": yolo_result.get("ok", False),
            "yolo_category": yolo_result.get("category", ""),
            "yolo_defect_type": yolo_result.get("defect_type", ""),
            "yolo_confidence": yolo_result.get("confidence", 0),
            "yolo_bbox_count": len(yolo_result.get("bboxes", [])),
            "will_upload": gate.will_upload,
            "reasons": gate.reasons,
            "meta": meta,
        }
        audit_rows.append(row)
        if gate.will_upload:
            valid_candidates.append((img_path, src_cat, meta))

    localizer.close()

    print(AUDIT_SEP)
    print("  Total: %d  Valid: %d  Blocked: %d" % (
        len(images), len(valid_candidates),
        len(images) - len(valid_candidates)))

    # Save audit.
    if args.output:
        with open(args.output, "w") as f:
            json.dump(audit_rows, f, indent=2)
        print("  Audit saved to %s" % args.output)

    # Dry-run: report candidate scan results.
    if args.mode == "dry-run":
        blocked = len(images) - len(valid_candidates)
        if blocked > 0 and not args.allow_ineligible:
            print("\nDRY-RUN FAILED: %d candidates blocked (use --allow-ineligible to override)." % blocked)
            sys.exit(1)
        elif blocked > 0:
            print("\nDRY-RUN PASSED (with %d ineligible): %d candidates valid." % (
                blocked, len(valid_candidates)))
        else:
            print("\nDRY-RUN PASSED: all %d candidates valid." % len(valid_candidates))
        return

    # Pre-soak: limit uploads.
    if args.mode == "pre-soak":
        candidates = valid_candidates[:args.limit]
        print("\n=== PRE-SOAK: uploading %d images ===" % len(candidates))
    else:
        candidates = valid_candidates
        print("\n=== FULL SOAK: uploading %d images ===" % len(candidates))

    # Upload and verify.
    results = []
    for i, (img_path, src_cat, meta) in enumerate(candidates):
        try:
            # Inject edge_ts at upload time with microsecond precision
            # to avoid UNIQUE constraint violations from same-second uploads.
            meta["edge_ts"] = time.strftime(
                "%Y-%m-%dT%H:%M:%S.", time.gmtime()) + "%06dZ" % (
                    int(time.time() * 1000000) % 1000000)
            upload = upload_defect(args.api, token, meta, img_path, args.timeout)
            defect_id = upload["id"]

            # Check enrichment lifecycle.
            enrich = check_enrichment(args.api, defect_id, args.enrich_timeout)
            enrich_status = enrich["status"] if enrich else "timeout"
            enrich_lat = enrich.get("_enrich_latency", 0) if enrich else 0

            # Verify canonical fields.
            canonical = check_canonical(args.api, defect_id)
            cat_ok = canonical["category"] == src_cat
            dt_ok = canonical["defect_type"] == meta["defect_type"]
            loc_ok = canonical.get("localization_source") == LOCALIZATION_SOURCE
            lbl_ok = canonical.get("label_source") == LABEL_SOURCE
            bbox_ok = len(canonical.get("bboxes", [])) > 0

            ok = all([cat_ok, dt_ok, loc_ok, lbl_ok, bbox_ok,
                      enrich_status == "complete"])

            results.append({
                "i": i, "defect_id": defect_id,
                "image": os.path.basename(img_path),
                "source_category": src_cat,
                "upload_latency": upload.get("_upload_latency", 0),
                "enrich_status": enrich_status,
                "enrich_latency": enrich_lat,
                "cat_ok": cat_ok, "dt_ok": dt_ok,
                "loc_ok": loc_ok, "lbl_ok": lbl_ok, "bbox_ok": bbox_ok,
                "observation_source": canonical.get("observation_source"),
            })

            status = "OK" if ok else "FAIL"
            print("  [%d/%d] id=%d %s/%s upload=%.1fs enrich=%.1fs %s" % (
                i + 1, len(candidates), defect_id, src_cat,
                meta["defect_type"], upload.get("_upload_latency", 0),
                enrich_lat, status))

        except Exception as e:
            results.append({"i": i, "error": str(e)[:200], "status": "error"})
            print("  [%d/%d] ERROR: %s" % (i + 1, len(candidates), str(e)[:100]))

    # Summary.
    ok_count = sum(1 for r in results if r.get("enrich_status") == "complete"
                   and r.get("cat_ok") and r.get("loc_ok"))
    err_count = sum(1 for r in results if r.get("status") == "error")
    fail_count = len(results) - ok_count - err_count

    upload_lats = sorted([r["upload_latency"] for r in results
                          if "upload_latency" in r])
    enrich_lats = sorted([r["enrich_latency"] for r in results
                          if "enrich_latency" in r])

    def pctl(arr, p):
        if not arr:
            return 0
        idx = int(len(arr) * p / 100)
        return arr[min(idx, len(arr) - 1)]

    print("\n=== PRE-SOAK SUMMARY ===" if args.mode == "pre-soak"
          else "\n=== FULL SOAK SUMMARY ===")
    print("  OK: %d  Fail: %d  Error: %d" % (ok_count, fail_count, err_count))
    if upload_lats:
        print("  Upload:    p50=%.1fs  p95=%.1fs" % (
            pctl(upload_lats, 50), pctl(upload_lats, 95)))
    if enrich_lats:
        print("  Enrich:    p50=%.1fs  p95=%.1fs" % (
            pctl(enrich_lats, 50), pctl(enrich_lats, 95)))
    print("  All loc_ok: %s" % all(r.get("loc_ok") for r in results if "loc_ok" in r))
    print("  All lbl_ok: %s" % all(r.get("lbl_ok") for r in results if "lbl_ok" in r))
    print("  All cat_ok: %s" % all(r.get("cat_ok") for r in results if "cat_ok" in r))

    if args.output:
        with open(args.output, "w") as f:
            json.dump({"audit": audit_rows, "results": results}, f, indent=2)
        print("  Results saved to %s" % args.output)


if __name__ == "__main__":
    main()
