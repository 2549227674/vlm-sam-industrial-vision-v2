# Phase 10 ORT CPU Fallback Snapshot Demo

This is a **static snapshot** of Phase 10 ORT (ONNX Runtime) CPU fallback detections
for frontend demo and merge-main presentation.

## What this is

- YOLOv8n-detect running via ONNX Runtime on CPU (not RKNN/NPU)
- Replaces FastSAM + VLM at T3 in the edge pipeline
- Produces structured detections: defect_type, category, confidence, bboxes
- Pipeline: EfficientAD-S (RKNN) → YOLOv8n-detect (ORT CPU) → Upload

## What this is NOT

- **NOT RKNN/NPU deployment** — RKNN localizer remains BLOCKED (rknn-toolkit2 2.3.2 issue)
- **NOT real-time** — this is a static snapshot, not a live stream
- **NOT VLM-powered** — VLM is not called; severity is fixed to "medium"

## Data fields

All records include v1.3 source tracking fields:
- `localization_source: "ort_yolov8n_cpu"` — identifies ORT CPU inference
- `label_source: "yolo_class_head"` — YOLO class head output (not VLM)
- `observation_source: "template"` — VLM not called
- `variant: "ort_2B"` — ORT localizer with 2B model size

## pipeline_ms.upload caveat

`pipeline_ms.upload` is 0.0 in edge payloads because the JSON meta is serialized
before the HTTP POST. The real upload_ms is measured after POST completes and logged
to stderr. This is a sequencing constraint, not a bug.

## Contents

- `manifest.json` — snapshot metadata and caveats
- `defects_snapshot.json` — 20 defect records (12 metal_nut + 8 cable)
- `stats_snapshot.json` — aggregated statistics
- `images/` — JPEG images copied from MVTec AD test set
