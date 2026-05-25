#!/usr/bin/env python3
"""Phase 10 RK3588 FP16 smoke test for YOLOv8n localizer.

Tests:
  1. Load RKNN model
  2. Run inference on 1 metal_nut + 1 cable image
  3. Decode YOLOv8 output (output0 [1, 16, 8400])
  4. Apply NMS
  5. Check bbox validity (0<=x,y,w,h<=1, x+w<=1, y+h<=1)
  6. Log latency per stage

Usage:
    python3 smoke_test_rknn.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import cv2
import numpy as np

# Paths
MODEL_PATH = Path("models/yolov8n_phase10/yolov8n_metal_nut_cable_best_fp16.rknn")
CLASSES_PATH = Path("configs/phase10_classes.yaml")
TEST_IMAGES = [
    ("datasets/phase10/images/val/metal_nut_bent_000.png", "metal_nut/bent"),
    ("datasets/phase10/images/val/cable_bent_wire_001.png", "cable/bent_wire"),
]

IMG_SIZE = 640
CONF_THRESH = 0.25
IOU_THRESH = 0.45
NUM_CLASSES = 12


def load_classes(path: Path) -> dict[int, str]:
    """Parse phase10_classes.yaml names dict."""
    names: dict[int, str] = {}
    in_names = False
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("names:"):
                in_names = True
                continue
            if in_names and line and line[0].isdigit():
                idx, name = line.split(":", 1)
                names[int(idx.strip())] = name.strip()
    return names


def letterbox(img: np.ndarray, new_size: int = 640) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Resize with padding (letterbox), return padded img, scale, (pad_w, pad_h)."""
    h, w = img.shape[:2]
    scale = min(new_size / h, new_size / w)
    nh, nw = int(h * scale), int(w * scale)
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((new_size, new_size, 3), 114, dtype=np.uint8)
    pad_h, pad_w = (new_size - nh) // 2, (new_size - nw) // 2
    canvas[pad_h : pad_h + nh, pad_w : pad_w + nw] = resized
    return canvas, scale, (pad_w, pad_h)


def xywh_to_xyxy(boxes: np.ndarray) -> np.ndarray:
    """Convert [cx, cy, w, h] to [x1, y1, x2, y2]."""
    out = np.empty_like(boxes)
    out[:, 0] = boxes[:, 0] - boxes[:, 2] / 2
    out[:, 1] = boxes[:, 1] - boxes[:, 3] / 2
    out[:, 2] = boxes[:, 0] + boxes[:, 2] / 2
    out[:, 3] = boxes[:, 1] + boxes[:, 3] / 2
    return out


def nms(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float) -> list[int]:
    """Simple NMS, returns kept indices."""
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
        inds = np.where(iou <= iou_thresh)[0]
        order = order[inds + 1]
    return keep


def decode_yolov8_output(
    output: np.ndarray, conf_thresh: float, img_size: int
) -> list[tuple[int, float, list[float]]]:
    """Decode YOLOv8 output0 [1, 16, 8400] -> list of (class_id, conf, [cx, cy, w, h])."""
    # output shape: [1, 4+num_classes, num_anchors] = [1, 16, 8400]
    preds = output[0]  # [16, 8400]
    boxes = preds[:4, :].T  # [8400, 4] cx cy w h (pixel coords)
    class_scores = preds[4:, :].T  # [8400, num_classes]

    # Max class score per anchor
    max_scores = class_scores.max(axis=1)  # [8400]
    class_ids = class_scores.argmax(axis=1)  # [8400]

    # Filter by confidence
    mask = max_scores > conf_thresh
    boxes = boxes[mask]
    max_scores = max_scores[mask]
    class_ids = class_ids[mask]

    if len(boxes) == 0:
        return []

    # Scale boxes from pixel to [0,1]
    boxes[:, 0] /= img_size
    boxes[:, 1] /= img_size
    boxes[:, 2] /= img_size
    boxes[:, 3] /= img_size

    # Convert to xyxy for NMS
    xyxy = xywh_to_xyxy(boxes)

    # NMS per class
    results: list[tuple[int, float, list[float]]] = []
    for cls in np.unique(class_ids):
        cls_mask = class_ids == cls
        cls_boxes = xyxy[cls_mask]
        cls_scores = max_scores[cls_mask]
        keep = nms(cls_boxes, cls_scores, IOU_THRESH)
        for k in keep:
            b = cls_boxes[k]
            cx = (b[0] + b[2]) / 2
            cy = (b[1] + b[3]) / 2
            w = b[2] - b[0]
            h = b[3] - b[1]
            results.append((int(cls), float(cls_scores[k]), [cx, cy, w, h]))

    return results


def check_bbox_valid(bbox: list[float]) -> tuple[bool, str]:
    """Check bbox validity: 0<=x,y,w,h<=1 and x+w<=1, y+h<=1."""
    cx, cy, w, h = bbox
    x1 = cx - w / 2
    y1 = cy - h / 2
    issues: list[str] = []
    if w < 0 or h < 0:
        issues.append(f"negative size: w={w:.4f} h={h:.4f}")
    if x1 < -0.01:
        issues.append(f"x1={x1:.4f} < 0")
    if y1 < -0.01:
        issues.append(f"y1={y1:.4f} < 0")
    if cx + w / 2 > 1.01:
        issues.append(f"x2={cx + w / 2:.4f} > 1")
    if cy + h / 2 > 1.01:
        issues.append(f"y2={cy + h / 2:.4f} > 1")
    if w > 1.01:
        issues.append(f"w={w:.4f} > 1")
    if h > 1.01:
        issues.append(f"h={h:.4f} > 1")
    return (len(issues) == 0, "; ".join(issues) if issues else "OK")


def main() -> None:
    print("=" * 60)
    print("Phase 10 RK3588 FP16 Smoke Test")
    print("=" * 60)

    # Check files
    for p in [MODEL_PATH, CLASSES_PATH]:
        if not p.exists():
            print(f"ERROR: {p} not found")
            sys.exit(1)
    for img_path, _ in TEST_IMAGES:
        if not Path(img_path).exists():
            print(f"ERROR: {img_path} not found")
            sys.exit(1)

    classes = load_classes(CLASSES_PATH)
    print(f"Classes: {len(classes)} ({', '.join(classes.values())})")

    # Import RKNN
    try:
        from rknnlite.api import RKNNLite
    except ImportError:
        print("ERROR: rknnlite not found. Install rknn-toolkit-lite2.")
        sys.exit(1)

    # Load model
    print(f"\nLoading model: {MODEL_PATH}")
    t0 = time.perf_counter()
    rknn = RKNNLite(verbose=False)
    ret = rknn.load_rknn(str(MODEL_PATH))
    if ret != 0:
        print(f"ERROR: load_rknn failed (ret={ret})")
        sys.exit(1)
    t_load = time.perf_counter() - t0
    print(f"  Load time: {t_load:.3f}s")

    # Init runtime
    print("Init runtime...")
    t0 = time.perf_counter()
    ret = rknn.init_runtime()
    if ret != 0:
        print(f"ERROR: init_runtime failed (ret={ret})")
        sys.exit(1)
    t_init = time.perf_counter() - t0
    print(f"  Init time: {t_init:.3f}s")

    # Run inference on each test image
    total_bbox_valid = 0
    total_bbox_invalid = 0
    total_crashes = 0
    latencies: dict[str, list[float]] = {
        "preprocess": [],
        "inference": [],
        "postprocess": [],
        "total": [],
    }

    for img_path, expected_class in TEST_IMAGES:
        print(f"\n{'='*60}")
        print(f"Image: {img_path}")
        print(f"Expected class: {expected_class}")

        # Preprocess
        t0 = time.perf_counter()
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"  ERROR: failed to read {img_path}")
            total_crashes += 1
            continue
        orig_h, orig_w = img.shape[:2]
        padded, scale, (pad_w, pad_h) = letterbox(img, IMG_SIZE)
        # BGR -> RGB, HWC -> CHW, add batch dim
        padded = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
        padded = np.transpose(padded, (2, 0, 1))  # HWC -> CHW
        padded = np.expand_dims(padded, axis=0)     # CHW -> NCHW
        t_pre = time.perf_counter() - t0

        # Inference
        t0 = time.perf_counter()
        outputs = rknn.inference(inputs=[padded])
        t_infer = time.perf_counter() - t0

        if outputs is None or len(outputs) == 0:
            print(f"  ERROR: inference returned None")
            total_crashes += 1
            continue

        output0 = outputs[0]
        print(f"  Output shape: {output0.shape}")

        # Postprocess
        t0 = time.perf_counter()
        detections = decode_yolov8_output(output0, CONF_THRESH, IMG_SIZE)
        t_post = time.perf_counter() - t0

        t_total = t_pre + t_infer + t_post
        latencies["preprocess"].append(t_pre)
        latencies["inference"].append(t_infer)
        latencies["postprocess"].append(t_post)
        latencies["total"].append(t_total)

        print(f"  Latency: pre={t_pre*1000:.1f}ms infer={t_infer*1000:.1f}ms post={t_post*1000:.1f}ms total={t_total*1000:.1f}ms")
        print(f"  Detections: {len(detections)}")

        for cls_id, conf, bbox in detections:
            cls_name = classes.get(cls_id, f"unknown_{cls_id}")
            valid, reason = check_bbox_valid(bbox)
            status = "OK" if valid else "INVALID"
            if valid:
                total_bbox_valid += 1
            else:
                total_bbox_invalid += 1
            print(f"    [{status}] {cls_name} conf={conf:.3f} bbox=[{bbox[0]:.4f}, {bbox[1]:.4f}, {bbox[2]:.4f}, {bbox[3]:.4f}] {reason}")

    # Cleanup
    rknn.release()

    # Summary
    print(f"\n{'='*60}")
    print("SMOKE TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Model:       {MODEL_PATH}")
    print(f"Model size:  {MODEL_PATH.stat().st_size / 1024 / 1024:.1f} MB")
    print(f"Test images: {len(TEST_IMAGES)}")
    print(f"Crashes:     {total_crashes}")
    print(f"Bbox valid:  {total_bbox_valid}")
    print(f"Bbox invalid:{total_bbox_invalid}")

    if latencies["total"]:
        print(f"\nLatency (ms):")
        for stage in ["preprocess", "inference", "postprocess", "total"]:
            vals = latencies[stage]
            avg = sum(vals) / len(vals) * 1000
            print(f"  {stage:12s}: avg={avg:.1f}")

    if total_crashes == 0 and total_bbox_invalid == 0 and total_bbox_valid > 0:
        print(f"\nRESULT: PASS")
    else:
        print(f"\nRESULT: FAIL (crashes={total_crashes}, invalid_bbox={total_bbox_invalid}, valid_bbox={total_bbox_valid})")
        sys.exit(1)


if __name__ == "__main__":
    main()
