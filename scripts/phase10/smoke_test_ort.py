#!/usr/bin/env python3
"""Phase 10 ONNX Runtime CPU smoke test for YOLOv8n localizer.

This is a CPU fallback for RK3588 where RKNN numeric consistency is BLOCKED.
Uses ONNX Runtime with CPUExecutionProvider to verify correctness.

Tests:
  1. Load ONNX model via onnxruntime
  2. Run inference on 1 metal_nut + 1 cable image
  3. Decode YOLOv8 output (output0 [1, 16, 8400])
  4. Apply NMS
  5. Check bbox validity (0<=x,y,w,h<=1, x+w<=1, y+h<=1)
  6. Compare top detection with PyTorch/ONNX reference
  7. Log latency per stage

Usage:
    # On PC (.venv):
    python scripts/phase10/smoke_test_ort.py

    # On RK3588 (after pip install onnxruntime):
    python3 smoke_test_ort.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_PATH = PROJECT_ROOT / "models" / "yolov8n_phase10" / "yolov8n_metal_nut_cable_best.onnx"
CLASSES_PATH = PROJECT_ROOT / "configs" / "phase10_classes.yaml"
TEST_IMAGES = [
    (PROJECT_ROOT / "datasets" / "phase10" / "images" / "val" / "metal_nut_bent_000.png", "metal_nut/bent"),
    (PROJECT_ROOT / "datasets" / "phase10" / "images" / "val" / "cable_bent_wire_001.png", "cable/bent_wire"),
]

IMG_SIZE = 640
CONF_THRESH = 0.25
IOU_THRESH = 0.45
NUM_CLASSES = 12

# PyTorch reference for metal_nut_bent_000 (from diagnostic report)
PYTORCH_REF = {
    "metal_nut_bent_000.png": {
        "class": "metal_nut/bent",
        "class_id": 0,
        "conf": 0.923,
        "bbox_norm": [0.8757, 0.5328, 0.1528, 0.1613],
    },
}


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
    preds = output[0]  # [16, 8400]
    boxes = preds[:4, :].T  # [8400, 4] cx cy w h (pixel coords)
    class_scores = preds[4:, :].T  # [8400, num_classes]

    max_scores = class_scores.max(axis=1)
    class_ids = class_scores.argmax(axis=1)

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

    xyxy = xywh_to_xyxy(boxes)

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


def compute_iou(a: list[float], b: list[float]) -> float:
    """Compute IoU between two [cx, cy, w, h] normalized bboxes."""
    ax1, ay1 = a[0] - a[2] / 2, a[1] - a[3] / 2
    ax2, ay2 = a[0] + a[2] / 2, a[1] + a[3] / 2
    bx1, by1 = b[0] - b[2] / 2, b[1] - b[3] / 2
    bx2, by2 = b[0] + b[2] / 2, b[1] + b[3] / 2

    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    area_a = a[2] * a[3]
    area_b = b[2] * b[3]
    union = area_a + area_b - inter
    return inter / (union + 1e-6)


def main() -> None:
    print("=" * 60)
    print("Phase 10 ONNX Runtime CPU Smoke Test")
    print("NOTE: This is a CPU fallback, NOT NPU/RKNN deployment.")
    print("      RKNN remains blocked pending toolkit investigation.")
    print("=" * 60)

    # Check files
    for p in [MODEL_PATH, CLASSES_PATH]:
        if not p.exists():
            print(f"ERROR: {p} not found")
            sys.exit(1)
    for img_path, _ in TEST_IMAGES:
        if not img_path.exists():
            print(f"ERROR: {img_path} not found")
            sys.exit(1)

    classes = load_classes(CLASSES_PATH)
    print(f"Classes: {len(classes)} ({', '.join(classes.values())})")

    # Import onnxruntime
    try:
        import onnxruntime as ort
    except ImportError:
        print("ERROR: onnxruntime not found. Install with: pip install onnxruntime")
        sys.exit(1)

    print(f"ONNX Runtime version: {ort.__version__}")
    print(f"Available providers: {ort.get_available_providers()}")

    # Load model
    print(f"\nLoading model: {MODEL_PATH}")
    t0 = time.perf_counter()
    sess = ort.InferenceSession(str(MODEL_PATH), providers=["CPUExecutionProvider"])
    t_load = time.perf_counter() - t0
    print(f"  Load time: {t_load:.3f}s")

    input_name = sess.get_inputs()[0].name
    output_name = sess.get_outputs()[0].name
    print(f"  Input:  {input_name} {sess.get_inputs()[0].shape}")
    print(f"  Output: {output_name} {sess.get_outputs()[0].shape}")

    # Run inference on each test image
    total_bbox_valid = 0
    total_bbox_invalid = 0
    total_crashes = 0
    class_correct = 0
    class_total = 0
    latencies: dict[str, list[float]] = {
        "preprocess": [],
        "inference": [],
        "postprocess": [],
        "total": [],
    }

    for img_path, expected_class in TEST_IMAGES:
        print(f"\n{'='*60}")
        print(f"Image: {img_path.name}")
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
        # BGR -> RGB, HWC -> CHW, float32 / 255
        padded = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
        padded = padded.astype(np.float32) / 255.0
        padded = np.transpose(padded, (2, 0, 1))  # HWC -> CHW
        padded = np.expand_dims(padded, axis=0)     # CHW -> NCHW
        t_pre = time.perf_counter() - t0

        # Inference
        t0 = time.perf_counter()
        outputs = sess.run([output_name], {input_name: padded})
        t_infer = time.perf_counter() - t0

        if outputs is None or len(outputs) == 0:
            print(f"  ERROR: inference returned None")
            total_crashes += 1
            continue

        output0 = outputs[0]
        print(f"  Output shape: {output0.shape}")
        print(f"  Output range: [{output0.min():.4f}, {output0.max():.4f}]")

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

        for cls_id, conf, bbox in detections[:5]:  # Show top 5
            cls_name = classes.get(cls_id, f"unknown_{cls_id}")
            valid, reason = check_bbox_valid(bbox)
            status = "OK" if valid else "INVALID"
            if valid:
                total_bbox_valid += 1
            else:
                total_bbox_invalid += 1
            print(f"    [{status}] {cls_name} conf={conf:.3f} bbox=[{bbox[0]:.4f}, {bbox[1]:.4f}, {bbox[2]:.4f}, {bbox[3]:.4f}] {reason}")

        # Check class correctness against reference
        if detections:
            top_cls_id, top_conf, top_bbox = detections[0]
            top_cls_name = classes.get(top_cls_id, f"unknown_{top_cls_id}")
            class_total += 1

            # Check against PyTorch reference
            ref_key = img_path.name
            if ref_key in PYTORCH_REF:
                ref = PYTORCH_REF[ref_key]
                if top_cls_name == ref["class"]:
                    class_correct += 1
                    iou = compute_iou(top_bbox, ref["bbox_norm"])
                    print(f"  REF CHECK: PASS (class={top_cls_name}, conf={top_conf:.3f} vs ref={ref['conf']:.3f}, IoU={iou:.3f})")
                else:
                    print(f"  REF CHECK: FAIL (got {top_cls_name}, expected {ref['class']})")
            else:
                # No reference, just check expected class
                if expected_class in top_cls_name:
                    class_correct += 1
                    print(f"  CLASS CHECK: PASS ({top_cls_name})")
                else:
                    print(f"  CLASS CHECK: FAIL (got {top_cls_name}, expected {expected_class})")

    # Summary
    print(f"\n{'='*60}")
    print("SMOKE TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Model:         {MODEL_PATH.name}")
    print(f"Model size:    {MODEL_PATH.stat().st_size / 1024 / 1024:.1f} MB")
    print(f"Provider:      CPUExecutionProvider")
    print(f"Test images:   {len(TEST_IMAGES)}")
    print(f"Crashes:       {total_crashes}")
    print(f"Bbox valid:    {total_bbox_valid}")
    print(f"Bbox invalid:  {total_bbox_invalid}")
    print(f"Class correct: {class_correct}/{class_total}")

    if latencies["total"]:
        print(f"\nLatency (ms):")
        for stage in ["preprocess", "inference", "postprocess", "total"]:
            vals = latencies[stage]
            avg = sum(vals) / len(vals) * 1000
            print(f"  {stage:12s}: avg={avg:.1f}")

    # Pass/Fail
    pass_conditions = [
        total_crashes == 0,
        total_bbox_invalid == 0,
        total_bbox_valid > 0,
        class_correct == class_total,
    ]
    if all(pass_conditions):
        print(f"\nRESULT: PASS")
        print("NOTE: This is a CPU fallback validation. RKNN NPU deployment remains blocked.")
    else:
        print(f"\nRESULT: FAIL")
        sys.exit(1)


if __name__ == "__main__":
    main()
