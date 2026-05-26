# Phase 10 v1 ORT Localizer Snapshot

Curated from 30-min soak test on Orange Pi 5 (RK3588). Real YOLOv8n-detect detections.

## What this is

- YOLOv8n-detect via ONNX Runtime on CPU (not RKNN/NPU)
- Replaces FastSAM + VLM at T3 in the edge pipeline
- 40 records: metal_nut (16) + cable (24), 12 defect types
- All confidence > 0, no fallback placeholder boxes

## What this is NOT

- NOT RKNN/NPU deployment — RKNN localizer remains BLOCKED
- NOT VLM-powered — VLM is not called; severity is fixed to "medium"
- NOT a full inspection pipeline — enrichment (observation/severity_reason) is Phase 10.1

## v1.3 Fields

- localization_source="ort_yolov8n_cpu"
- label_source="yolo_class_head"
- observation_source="template"
- pipeline_ms.localizer (avg ~188ms)
- trace_events with T3.localizer lane

## pipeline_ms.upload Caveat

upload=0.0 in payload because JSON meta is serialized before HTTP POST.
Real upload_ms measured after POST and logged to stderr.

## Contents

- manifest.json — metadata + caveats
- defects_snapshot.json — 40 curated records
- stats_snapshot.json — aggregated stats
- images/ — 40 JPEG images from soak test
