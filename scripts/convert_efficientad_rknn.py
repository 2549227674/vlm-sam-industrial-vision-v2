#!./.venv_rknn/bin/python3
"""Stage 6.2: Convert EfficientAD-S ONNX to RKNN INT8 for RK3588.

Requires: rknn-toolkit2 in .venv_rknn (NOT .venv)
Runs on:  PC or cross-compile host (not on RK3588 itself)

Input:  models/efficientad_models/{category}/weights/onnx/model.onnx
        (or model_raw.onnx with --use-raw-onnx)
Output: models/efficientad_models/{category}/model.rknn
        models/efficientad_models/{category}/accuracy_analysis/

Old v1 3-class archives in models/efficientad_models_v1_3cls/ are NOT touched.

Normalization: ImageNet defaults used by Anomalib
    mean=[123.675, 116.28, 103.53], std=[58.395, 57.12, 57.375]

Usage:
    source .venv_rknn/bin/activate
    python scripts/convert_efficientad_rknn.py                     # all 15 classes
    python scripts/convert_efficientad_rknn.py --categories metal_nut
    python scripts/convert_efficientad_rknn.py --categories bottle cable zipper
    python scripts/convert_efficientad_rknn.py --calib-samples 100
    python scripts/convert_efficientad_rknn.py --skip-accuracy-analysis
    python scripts/convert_efficientad_rknn.py --dry-run            # pre-check only
    python scripts/convert_efficientad_rknn.py --dry-run --categories metal_nut
    python scripts/convert_efficientad_rknn.py --use-raw-onnx --categories bottle
    python scripts/convert_efficientad_rknn.py --use-raw-onnx --dry-run
    python scripts/convert_efficientad_rknn.py --use-raw-onnx --no-quant --categories bottle
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models" / "efficientad_models"
MVTEC_DIR = PROJECT_ROOT / "simulator" / "mvtec"

# MVTec AD full 15 classes
CATEGORIES = [
    "bottle", "cable", "capsule", "carpet", "grid",
    "hazelnut", "leather", "metal_nut", "pill", "screw",
    "tile", "toothbrush", "transistor", "wood", "zipper",
]
CATEGORY_SET = frozenset(CATEGORIES)
MIN_CALIB_SAMPLES = 50
COSINE_THRESHOLD = 0.99

# Anomalib ImageNet normalization (RGB, 0-255 range)
MEAN_VALUES = [[123.675, 116.28, 103.53]]
STD_VALUES = [[58.395, 57.12, 57.375]]


def create_calib_list(category: str, num_samples: int) -> str:
    """Write absolute paths of good/ images to a text file for RKNN calibration."""
    good_dir = MVTEC_DIR / category / "train" / "good"
    if not good_dir.exists():
        raise FileNotFoundError(f"Calibration dir not found: {good_dir}")

    images = sorted(good_dir.glob("*.png"))[:num_samples]
    if len(images) < MIN_CALIB_SAMPLES:
        raise ValueError(
            f"{category}: need >= {MIN_CALIB_SAMPLES} calib images, found {len(images)} in {good_dir}"
        )

    calib_file = MODELS_DIR / category / "calib_dataset.txt"
    calib_file.parent.mkdir(parents=True, exist_ok=True)
    with open(calib_file, "w") as f:
        for img in images:
            f.write(f"{img.resolve()}\n")

    print(f"  Calibration list: {len(images)} images -> {calib_file}")
    return str(calib_file)


def parse_accuracy_report(analysis_dir: Path) -> dict:
    """Parse error_analysis.txt with output-layer-aware cosine reporting.

    Returns dict with keys:
        min_cosine:         minimum entire-cosine across ALL layers
        output_layer_cosine: entire-cosine for the final output tensor (anomaly_map or pred_score)
        output_layer_name:  name of the matched output layer, or None
        all_pass:           True if min_cosine >= COSINE_THRESHOLD

    Table row format (rknn-toolkit2 v2.3.2):
      [Conv] /model.0/...   0.99858 | 504.43    0.99858 | 504.43
      entire cos ^                 ^ single cos
    """
    report_path = analysis_dir / "error_analysis.txt"
    result = {
        "min_cosine": 0.0,
        "output_layer_cosine": None,
        "output_layer_name": None,
        "all_pass": False,
    }
    if not report_path.exists():
        print(f"  WARNING: report not found at {report_path}")
        return result

    # group(1) = entire cosine, group(2) = single cosine
    row_pattern = re.compile(r"^\[.*?\].*?\s+([\d.]+)\s+\|\s+[\d.]+\s+([\d.]+)")
    # EfficientAD final outputs: /anomaly_map/... or /pred_score/...
    output_pattern = re.compile(r"/(anomaly_map|pred_score)")

    min_cosine = 1.0
    output_layer_cosine: float | None = None
    output_layer_name: str | None = None

    with open(report_path) as f:
        for line in f:
            m = row_pattern.search(line)
            if not m:
                continue
            val = float(m.group(1))  # entire cosine
            if val < min_cosine:
                min_cosine = val
            om = output_pattern.search(line)
            if om:
                output_layer_cosine = val
                output_layer_name = om.group(1)

    result["min_cosine"] = min_cosine
    result["output_layer_cosine"] = output_layer_cosine
    result["output_layer_name"] = output_layer_name
    result["all_pass"] = min_cosine >= COSINE_THRESHOLD
    return result


def dry_run_check(categories: list[str], calib_samples: int,
                  use_raw_onnx: bool = False) -> None:
    """Pre-check: verify ONNX and calibration images exist without running RKNN."""
    onnx_label = "model_raw.onnx" if use_raw_onnx else "model.onnx"
    print(f"\n{'=' * 50}")
    print(f"  DRY-RUN: Pre-check (use_raw_onnx={use_raw_onnx})")
    print(f"{'=' * 50}")
    print(f"  ONNX target: {onnx_label}")
    print(f"  Calib samples threshold: {MIN_CALIB_SAMPLES}")
    print()

    onnx_ok: list[str] = []
    onnx_missing: list[str] = []
    calib_warn: list[str] = []

    for cat in categories:
        onnx_path = MODELS_DIR / cat / "weights" / "onnx" / onnx_label
        rknn_path = MODELS_DIR / cat / "model.rknn"
        good_dir = MVTEC_DIR / cat / "train" / "good"

        has_onnx = onnx_path.exists()
        n_images = len(list(good_dir.glob("*.png"))) if good_dir.exists() else 0

        onnx_status = "OK" if has_onnx else "MISSING"
        calib_status = f"{n_images} images"
        if n_images < MIN_CALIB_SAMPLES:
            calib_status += " (WARN: < {})".format(MIN_CALIB_SAMPLES)
            calib_warn.append(cat)

        if has_onnx:
            onnx_ok.append(cat)
        else:
            onnx_missing.append(cat)

        print(f"  {cat:14s}  ONNX={onnx_status:7s}  calib={calib_status:20s}  -> {rknn_path}")

    print(f"\n  {'=' * 50}")
    print(f"  Dry-run Summary")
    print(f"  {'=' * 50}")
    print(f"  ONNX existing:  {len(onnx_ok)}/{len(categories)}")
    print(f"  ONNX missing:   {len(onnx_missing)}/{len(categories)}")
    if onnx_missing:
        print(f"    missing: {', '.join(onnx_missing)}")
    if calib_warn:
        print(f"  Calib warning (< {MIN_CALIB_SAMPLES}): {', '.join(calib_warn)}")
    if onnx_ok:
        print(f"  Convertible:    {', '.join(onnx_ok)}")
    else:
        print(f"  Convertible:    (none — run Phase 5.1 training first)")


def convert_category(category: str, calib_samples: int,
                     skip_accuracy_analysis: bool = False,
                     use_raw_onnx: bool = False,
                     no_quant: bool = False) -> bool:
    """Convert one category. Returns True on success (RKNN exported).

    Order: config → load → build → export → accuracy_analysis (optional).
    A failure in accuracy_analysis does NOT invalidate an already-exported model.
    """
    from rknn.api import RKNN

    onnx_name = "model_raw.onnx" if use_raw_onnx else "model.onnx"
    onnx_path = MODELS_DIR / category / "weights" / "onnx" / onnx_name

    # Output path: no-quant raw models go to a separate file to avoid
    # overwriting the production INT8 model.rknn.
    if no_quant:
        rknn_path = MODELS_DIR / category / "model_raw_noquant.rknn"
    else:
        rknn_path = MODELS_DIR / category / "model.rknn"

    # Raw model outputs: raw_score [1,1] + raw_anomaly_map [1,1,256,256]
    # Legacy model outputs: pred_score + anomaly_map (post-processed, clipped)
    if use_raw_onnx:
        rknn_outputs = ["raw_score", "raw_anomaly_map"]
    else:
        rknn_outputs = ["pred_score", "anomaly_map"]

    if not onnx_path.exists():
        print(f"  [SKIP] ONNX not found: {onnx_path}")
        return False

    # Step count: no-quant skips calibration and accuracy analysis.
    if no_quant:
        total_steps = 4  # config, load, build, export
    elif skip_accuracy_analysis:
        total_steps = 4
    else:
        total_steps = 5

    print(f"\n{'=' * 50}")
    print(f"  Converting: {category}")
    print(f"{'=' * 50}")
    print(f"  using_raw_onnx={use_raw_onnx}")
    print(f"  no_quant={no_quant}")
    print(f"  onnx_path={onnx_path}")
    print(f"  rknn_output_path={rknn_path}")
    print(f"  outputs={rknn_outputs}")

    rknn = RKNN(verbose=False)

    try:
        # 1. Config
        step = 0
        if no_quant:
            step += 1
            print(f"  [{step}/{total_steps}] Config (FP16 no-quant, rk3588)...")
            ret = rknn.config(
                mean_values=MEAN_VALUES,
                std_values=STD_VALUES,
                target_platform="rk3588",
            )
        else:
            step += 1
            print(f"  [{step}/{total_steps}] Config (INT8, rk3588)...")
            ret = rknn.config(
                mean_values=MEAN_VALUES,
                std_values=STD_VALUES,
                target_platform="rk3588",
                quantized_dtype="asymmetric_quantized-8",
            )
        if ret != 0:
            print("  FAIL: config()")
            return False

        # 2. Load ONNX
        step += 1
        print(f"  [{step}/{total_steps}] Load ONNX (outputs={rknn_outputs})...")
        ret = rknn.load_onnx(
                model=str(onnx_path),
                inputs=['input'],
                input_size_list=[[1, 3, 256, 256]],
		outputs=rknn_outputs,
        )
        if ret != 0:
            print("  FAIL: load_onnx()")
            return False

        # 3. Build
        step += 1
        if no_quant:
            print(f"  [{step}/{total_steps}] Build FP16 (no quantization)...")
            ret = rknn.build(do_quantization=False)
        else:
            print(f"  [{step}/{total_steps}] Build INT8 (calib={calib_samples} samples)...")
            calib_file = create_calib_list(category, calib_samples)
            ret = rknn.build(do_quantization=True, dataset=calib_file)
        if ret != 0:
            print("  FAIL: build()")
            return False

        # 4. Export
        step += 1
        print(f"  [{step}/{total_steps}] Export RKNN -> {rknn_path}...")
        ret = rknn.export_rknn(str(rknn_path))
        if ret != 0:
            print("  FAIL: export_rknn()")
            return False

        print(f"  Exported: {rknn_path}")

        if no_quant or skip_accuracy_analysis:
            reason = "no-quant mode" if no_quant else "--skip-accuracy-analysis"
            print(f"  Accuracy analysis: SKIPPED ({reason})")
            return True

        # 5. Accuracy analysis (optional, failure non-fatal)
        analysis_dir = MODELS_DIR / category / "accuracy_analysis"
        analysis_dir.mkdir(parents=True, exist_ok=True)

        step += 1
        print(f"  [{step}/{total_steps}] Accuracy analysis...")
        try:
            with open(calib_file) as f:
                first_image = f.readline().strip()
            rknn.accuracy_analysis(inputs=[first_image], output_dir=str(analysis_dir))

            report = parse_accuracy_report(analysis_dir)
            min_cos = report["min_cosine"]
            out_cos = report["output_layer_cosine"]
            out_name = report["output_layer_name"]

            print(f"  Min cosine (all layers): {min_cos:.5f}")
            if out_cos is not None and out_name:
                status = "OK" if out_cos >= COSINE_THRESHOLD else "BELOW THRESHOLD"
                print(f"  Output layer ({out_name}): {out_cos:.5f}  [{status}]")
            if not report["all_pass"]:
                print(f"  WARNING: min cosine below threshold {COSINE_THRESHOLD}")
        except Exception as e:
            print(f"  WARNING: accuracy_analysis failed ({e})")
            print(f"  Exported model at {rknn_path} is unaffected.")

        return True

    finally:
        rknn.release()


def main() -> None:
    parser = argparse.ArgumentParser(description="EfficientAD-S ONNX -> RKNN INT8 (15 classes)")
    parser.add_argument("--categories", nargs="+", default=CATEGORIES,
                        help="Categories to convert (default: all 15 MVTec classes)")
    parser.add_argument("--calib-samples", type=int, default=100,
                        help="Number of good/ images for INT8 calibration")
    parser.add_argument("--skip-accuracy-analysis", action="store_true",
                        help="Skip accuracy_analysis after export (faster, model.rknn still valid)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Pre-check only: verify ONNX and calib images without RKNN conversion")
    parser.add_argument("--use-raw-onnx", action="store_true",
                        help="Use model_raw.onnx (pre-postprocessor) instead of model.onnx")
    parser.add_argument("--no-quant", action="store_true",
                        help="Build without INT8 quantization (FP16). Requires --use-raw-onnx. "
                             "Output: model_raw_noquant.rknn (does not overwrite model.rknn)")
    args = parser.parse_args()

    # Validate categories against whitelist
    invalid = [c for c in args.categories if c not in CATEGORY_SET]
    if invalid:
        print(f"ERROR: invalid categories: {invalid}")
        print(f"Allowed: {sorted(CATEGORY_SET)}")
        sys.exit(1)

    if args.no_quant and not args.use_raw_onnx:
        print("ERROR: --no-quant requires --use-raw-onnx")
        sys.exit(1)

    if args.dry_run:
        dry_run_check(args.categories, args.calib_samples, args.use_raw_onnx)
        return

    results: dict[str, bool | str] = {}

    for cat in args.categories:
        try:
            ok = convert_category(cat, args.calib_samples,
                                  args.skip_accuracy_analysis,
                                  args.use_raw_onnx,
                                  args.no_quant)
            results[cat] = ok
        except Exception as e:
            print(f"  ERROR ({cat}): {e}")
            results[cat] = "ERROR"

    # Summary
    print(f"\n{'=' * 50}")
    print("  Summary")
    print(f"{'=' * 50}")
    pass_count = 0
    fail_count = 0
    skip_count = 0
    for cat, val in results.items():
        if val is True:
            print(f"  {cat:14s}  PASS")
            pass_count += 1
        elif val is False:
            print(f"  {cat:14s}  FAIL")
            fail_count += 1
        else:
            print(f"  {cat:14s}  {val}")
            skip_count += 1

    total = len(results)
    print(f"\n  PASS={pass_count}  FAIL={fail_count}  SKIP/ERROR={skip_count}  total={total}")
    if args.skip_accuracy_analysis:
        print("  Accuracy analysis: SKIPPED")
    else:
        print(f"  Threshold: cosine >= {COSINE_THRESHOLD}")

    if fail_count > 0 or skip_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
