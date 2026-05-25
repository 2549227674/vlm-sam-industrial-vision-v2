# Phase 10 Training Runs

> Template for recording YOLOv8n-detect training runs.
> Fill in after training completes.

## Preflight Status (2026-05-25)

**Data pipeline:** COMPLETE
- `mvtec_mask_to_yolo.py`: 185 images, 283 bboxes, 0 filtered
- `split_mvtec_localization.py`: 126 train, 59 val (seed=42, ratio=0.7)
- `visualize_yolo_labels.py`: 50 val QA images with bbox + GT mask overlay

**QA checks:** PASS
- All 12 classes have labels
- 0 empty labels
- metal_nut mask overlay renders correctly
- cable/cut_outer_insulation parses correctly (underscore in defect_type)
- Bboxes cover defects, not whole objects (except metal_nut/flip — expected)
- No anomaly filtering needed (all components >= 16px^2)

**Known data characteristics:**
- metal_nut/flip: large bboxes (~85% area) — object-level pose anomaly, not localized defect
- cable/combined: multi-component, avg 3.7 bboxes/image
- cable/bent_wire (13 images) and cable/missing_wire (10 images): small sample classes

**Ready for training:** YES — awaiting GPU compute (local or AutoDL)

## Run 1: YOLOv8n 640 baseline

**Status:** PENDING (awaiting GPU compute)

| Parameter | Value |
|---|---|
| Model | yolov8n.pt |
| Dataset | datasets/phase10/phase10.yaml |
| Image size | 640 |
| Epochs | 100 |
| Batch | 16 |
| Seed | 42 |
| Patience | 20 |
| Device | TBD (local GPU or AutoDL) |
| Start time | — |
| End time | — |
| Duration | — |

### Per-Class AP (pending)

| Class | AP@0.5 | AP@0.5:0.95 | Notes |
|---|---:|---:|---|
| metal_nut/bent | — | — | |
| metal_nut/color | — | — | |
| metal_nut/flip | — | — | Object-level anomaly, may need special handling |
| metal_nut/scratch | — | — | |
| cable/bent_wire | — | — | Small sample count (13) |
| cable/cable_swap | — | — | |
| cable/combined | — | — | Multi-component |
| cable/cut_inner_insulation | — | — | |
| cable/cut_outer_insulation | — | — | |
| cable/missing_cable | — | — | |
| cable/missing_wire | — | — | |
| cable/poke_insulation | — | — | |
| **Overall mAP@0.5** | **—** | — | Target: >= 0.55 |

### ONNX / RKNN Export (pending)

| Format | Size | Notes |
|---|---|---|
| PyTorch best.pt | — | |
| ONNX | — | |
| RKNN FP16 | — | |
| RKNN INT8 | — | |

### ONNX vs RKNN Delta (pending)

| Class | PyTorch AP | ONNX AP | RKNN FP16 AP | RKNN INT8 AP | FP16 delta | INT8 delta |
|---|---:|---:|---:|---:|---:|---:|
| (pending) | | | | | | |

### RK3588 Latency (pending)

| Metric | Value |
|---|---|
| NPU inference (ms) | — |
| Total with pre/post (ms) | — |
| RSS (MB) | — |

## Decision Thresholds

- If overall mAP@0.5 < 0.55 after tuning: scale to YOLOv8s
- If RKNN INT8 AP delta > 10%: ship FP16/no-quant
- If `metal_nut/flip` AP very low: mark as object-level anomaly, exclude from main metrics
- If `cable/bent_wire` AP very low: document as low-sample class
