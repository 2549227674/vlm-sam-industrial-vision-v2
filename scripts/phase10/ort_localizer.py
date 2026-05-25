#!/usr/bin/env python3
"""ONNX Runtime CPU localizer subprocess for edge pipeline.

Reads image paths from stdin (one per line), runs YOLOv8n inference,
writes JSON results to stdout (one JSON object per line).

Designed to be spawned once by C++ LocalizerWorker and kept alive
for the duration of the pipeline.

Usage:
    python3 ort_localizer.py --model <onnx> --classes <yaml> [--conf 0.25] [--iou 0.45]

Protocol:
    stdin:  one image path per line
    stdout: one JSON object per line (same order)
    stderr: diagnostic logs

Exit codes:
    0 = clean shutdown (stdin closed)
    1 = fatal error (model load failed, etc.)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ORT localizer subprocess")
    p.add_argument("--model", required=True, help="Path to ONNX model")
    p.add_argument("--classes", required=True, help="Path to classes YAML")
    p.add_argument("--conf", type=float, default=0.25, help="Confidence threshold")
    p.add_argument("--iou", type=float, default=0.45, help="NMS IoU threshold")
    p.add_argument("--img-size", type=int, default=640, help="Input image size")
    return p.parse_args()


def load_classes(path: Path) -> dict[int, dict[str, str]]:
    """Parse classes YAML -> {class_id: {full_name, category, defect_type}}."""
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

    result: dict[int, dict[str, str]] = {}
    for cid, full_name in names.items():
        if "/" in full_name:
            category, defect_type = full_name.split("/", 1)
        else:
            category, defect_type = full_name, full_name
        result[cid] = {
            "full_name": full_name,
            "category": category,
            "defect_type": defect_type,
        }
    return result


def letterbox(img: np.ndarray, new_size: int) -> tuple[np.ndarray, float, tuple[int, int]]:
    h, w = img.shape[:2]
    scale = min(new_size / h, new_size / w)
    nh, nw = int(h * scale), int(w * scale)
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((new_size, new_size, 3), 114, dtype=np.uint8)
    pad_h, pad_w = (new_size - nh) // 2, (new_size - nw) // 2
    canvas[pad_h : pad_h + nh, pad_w : pad_w + nw] = resized
    return canvas, scale, (pad_w, pad_h)


def xywh_to_xyxy(boxes: np.ndarray) -> np.ndarray:
    out = np.empty_like(boxes)
    out[:, 0] = boxes[:, 0] - boxes[:, 2] / 2
    out[:, 1] = boxes[:, 1] - boxes[:, 3] / 2
    out[:, 2] = boxes[:, 0] + boxes[:, 2] / 2
    out[:, 3] = boxes[:, 1] + boxes[:, 3] / 2
    return out


def nms(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float) -> list[int]:
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        if order.size == 1:
            break
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
        inds = np.where(iou <= iou_thresh)[0]
        order = order[inds + 1]
    return keep


def decode(output: np.ndarray, conf_thresh: float, img_size: int,
           nms_iou: float) -> list[tuple[int, float, list[float]]]:
    """Decode YOLOv8 output [1, 16, 8400] -> sorted by conf desc."""
    preds = output[0]
    boxes = preds[:4, :].T
    class_scores = preds[4:, :].T
    max_scores = class_scores.max(axis=1)
    class_ids = class_scores.argmax(axis=1)

    mask = max_scores > conf_thresh
    boxes, max_scores, class_ids = boxes[mask], max_scores[mask], class_ids[mask]
    if len(boxes) == 0:
        return []

    boxes[:, 0] /= img_size
    boxes[:, 1] /= img_size
    boxes[:, 2] /= img_size
    boxes[:, 3] /= img_size
    xyxy = xywh_to_xyxy(boxes)

    results: list[tuple[int, float, list[float]]] = []
    for cls in np.unique(class_ids):
        cm = class_ids == cls
        keep = nms(xyxy[cm], max_scores[cm], nms_iou)
        cls_boxes = xyxy[cm]
        cls_scores = max_scores[cm]
        for k in keep:
            b = cls_boxes[k]
            # Convert xyxy to top-left xywh (API contract: x,y = top-left corner)
            # Clamp to [0, 1] to prevent API validation errors
            x = max(0.0, min(1.0, float(b[0])))
            y = max(0.0, min(1.0, float(b[1])))
            w = max(0.0, min(1.0 - x, float(b[2] - b[0])))
            h = max(0.0, min(1.0 - y, float(b[3] - b[1])))
            if w > 0.0 and h > 0.0:
                results.append((int(cls), float(cls_scores[k]), [x, y, w, h]))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def process_image(sess, input_name: str, output_name: str,
                  image_path: str, classes: dict,
                  conf_thresh: float, nms_iou: float,
                  img_size: int) -> dict:
    """Run inference on one image, return result dict."""
    t0 = time.perf_counter()

    img = cv2.imread(image_path)
    if img is None:
        import os
        exists = os.path.exists(image_path)
        return {"image_path": image_path, "ok": False,
                "error": "image_read_failed exists=%s path=%s" % (exists, image_path)}

    padded, _, _ = letterbox(img, img_size)
    padded = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
    padded = padded.astype(np.float32) / 255.0
    padded = np.transpose(padded, (2, 0, 1))[np.newaxis, ...]
    t_pre = time.perf_counter() - t0

    t1 = time.perf_counter()
    outputs = sess.run([output_name], {input_name: padded})
    t_infer = time.perf_counter() - t1

    t2 = time.perf_counter()
    detections = decode(outputs[0], conf_thresh, img_size, nms_iou)
    t_post = time.perf_counter() - t2

    t_total = t_pre + t_infer + t_post

    if not detections:
        return {
            "image_path": image_path, "ok": True,
            "defect_type": "anomaly", "confidence": 0.0,
            "bboxes": [], "class_id": -1, "class_name": "unknown",
            "preprocess_ms": round(t_pre * 1000, 1),
            "inference_ms": round(t_infer * 1000, 1),
            "postprocess_ms": round(t_post * 1000, 1),
            "total_ms": round(t_total * 1000, 1),
        }

    top_cls, top_conf, top_bbox = detections[0]
    info = classes.get(top_cls, {"full_name": "unknown", "category": "unknown",
                                  "defect_type": "anomaly"})

    bboxes = [{"x": round(float(b[2][0]), 6), "y": round(float(b[2][1]), 6),
               "w": round(float(b[2][2]), 6), "h": round(float(b[2][3]), 6)}
              for b in detections]

    return {
        "image_path": image_path,
        "ok": True,
        "defect_type": info["defect_type"],
        "confidence": round(float(top_conf), 6),
        "bboxes": bboxes,
        "class_id": int(top_cls),
        "class_name": info["full_name"],
        "category": info["category"],
        "preprocess_ms": round(t_pre * 1000, 1),
        "inference_ms": round(t_infer * 1000, 1),
        "postprocess_ms": round(t_post * 1000, 1),
        "total_ms": round(t_total * 1000, 1),
    }


def main() -> None:
    args = parse_args()

    model_path = Path(args.model)
    classes_path = Path(args.classes)

    if not model_path.exists():
        print(json.dumps({"ok": False, "error": f"model not found: {model_path}"}),
              flush=True)
        sys.exit(1)
    if not classes_path.exists():
        print(json.dumps({"ok": False, "error": f"classes not found: {classes_path}"}),
              flush=True)
        sys.exit(1)

    classes = load_classes(classes_path)

    import onnxruntime as ort
    sess = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    input_name = sess.get_inputs()[0].name
    output_name = sess.get_outputs()[0].name

    # Signal readiness to parent.
    print(json.dumps({"ready": True, "model": str(model_path),
                       "classes": len(classes)}), flush=True)

    # Warmup: run one dummy inference to pre-allocate ORT buffers.
    dummy = np.zeros((1, 3, args.img_size, args.img_size), dtype=np.float32)
    sess.run([output_name], {input_name: dummy})

    # Use readline() instead of `for line in sys.stdin:` to avoid
    # Python's read-ahead buffering, which causes deadlock when the
    # parent sends one path at a time and waits for the result.
    while True:
        line = sys.stdin.readline()
        if not line:
            break  # stdin closed (EOF)
        path = line.strip()
        if not path:
            continue
        if path == "__EXIT__":
            break

        try:
            result = process_image(
                sess, input_name, output_name,
                path, classes, args.conf, args.iou, args.img_size)
        except Exception as e:
            import traceback
            traceback.print_exc(file=sys.stderr)
            result = {"image_path": path, "ok": False,
                      "error": "exception: %s" % str(e)}
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
