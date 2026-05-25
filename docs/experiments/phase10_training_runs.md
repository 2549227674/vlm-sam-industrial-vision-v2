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

**Status:** COMPLETE

| Parameter | Value |
|---|---|
| Model | yolov8n.pt |
| Dataset | datasets/phase10/phase10.yaml |
| Image size | 640 |
| Epochs | 100 (stopped at 85, early stopping patience=20) |
| Batch | 16 |
| Seed | 42 |
| Patience | 20 |
| Device | AutoDL RTX 4090 48GB |
| Start time | 2026-05-25 20:55 CST |
| End time | 2026-05-25 21:02 CST |
| Duration | ~7 minutes |

### Per-Class AP (epoch 65, best.pt)

| Class | AP@0.5 | AP@0.5:0.95 | Notes |
|---|---:|---:|---|
| metal_nut/bent | 0.647 | 0.437 | |
| metal_nut/color | 0.830 | 0.614 | |
| metal_nut/flip | 0.995 | 0.895 | Object-level anomaly, near-perfect |
| metal_nut/scratch | 0.463 | 0.214 | Thin scratches, moderate |
| cable/bent_wire | 0.522 | 0.310 | Small sample count (13) |
| cable/cable_swap | 0.682 | 0.558 | |
| cable/combined | 0.338 | 0.112 | Multi-component, very low recall |
| cable/cut_inner_insulation | 0.540 | 0.417 | |
| cable/cut_outer_insulation | 0.239 | 0.183 | Very low recall, small defect |
| cable/missing_cable | 0.995 | 0.833 | Near-perfect |
| cable/missing_wire | 0.583 | 0.466 | |
| cable/poke_insulation | 0.287 | 0.146 | Low recall, small defect |
| **Overall mAP@0.5** | **0.593** | **0.432** | **Target >= 0.55: PASS** |

### ONNX / RKNN Export (pending)

| Format | Size | Notes |
|---|---|---|
| PyTorch best.pt | 6.3 MB | `models/yolov8n_phase10/yolov8n_metal_nut_cable_best.pt` |
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

### Inference Speed (PyTorch, RTX 4090)

| Stage | Time |
|---|---|
| Preprocess | 0.1 ms |
| Inference | 0.3 ms |
| Postprocess | 0.4 ms |
| **Total** | **0.8 ms** (~1250 FPS) |

## Decision Thresholds

- If overall mAP@0.5 < 0.55 after tuning: scale to YOLOv8s
- If RKNN INT8 AP delta > 10%: ship FP16/no-quant
- If `metal_nut/flip` AP very low: mark as object-level anomaly, exclude from main metrics
- If `cable/bent_wire` AP very low: document as low-sample class

## Run 1 Decisions

- **mAP@0.5 = 0.593 >= 0.55**: PASS, no need to scale to YOLOv8s
- **metal_nut/flip AP = 0.995**: Near-perfect, no special handling needed
- **cable/bent_wire AP = 0.522**: Moderate, acceptable for low-sample class
- **Weak classes identified**: cable/combined (0.338), cable/cut_outer_insulation (0.239), cable/poke_insulation (0.287) — may benefit from per-class threshold tuning or additional augmentation
- **Next steps**: Export to ONNX → RKNN, test on RK3588
