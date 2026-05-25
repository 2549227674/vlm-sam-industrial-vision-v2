# Phase 10 v1 — ONNX Runtime CPU Fallback Plan

## Status: ACTIVE — CPU fallback for blocked RKNN

## Context

RKNN numeric consistency is BLOCKED for YOLOv8 detection head (see
`phase10_rknn_fp16_diagnostic.md`). Both standard Ultralytics single-output and
airockchip multi-output RKNN FP16 paths produce corrupted class scores.

This plan implements ONNX Runtime CPU inference on RK3588 as a correctness
baseline and interim deployment path.

## Scope

- **Target**: metal_nut + cable (2 classes, 12 defect types)
- **Model**: YOLOv8n ONNX (opset=19, 11.7 MB)
- **Runtime**: ONNX Runtime with CPUExecutionProvider
- **Platform**: RK3588 (Orange Pi 5 16GB) ARM64 Linux

## Acceptance Criteria

| Gate | Criterion | Source |
|------|-----------|--------|
| Class correctness | Top-1 class matches PyTorch reference | PyTorch ref: metal_nut/bent conf=0.923 |
| Bbox validity | All bboxes satisfy 0<=x,y,w,h<=1 | `check_bbox_valid()` |
| Bbox IoU | Top detection IoU > 0.7 vs PyTorch ref | `compute_iou()` |
| Latency | Total < 500ms per frame | Target for CPU fallback |
| Stability | 0 crashes over 10+ images | Smoke test |

## Steps

### 1. ONNX Runtime Installation on RK3588

```bash
# On Orange Pi 5:
pip3 install onnxruntime

# Verify
python3 -c "import onnxruntime as ort; print(ort.__version__); print(ort.get_available_providers())"
# Expected: ['CPUExecutionProvider']
```

Note: `onnxruntime-gpu` is NOT available for RK3588 (no CUDA). The stock
`onnxruntime` package provides CPUExecutionProvider on ARM64.

### 2. Smoke Test (`smoke_test_ort.py`)

Script: `scripts/phase10/smoke_test_ort.py`

Tests:
1. Load ONNX model via `onnxruntime.InferenceSession`
2. Run inference on `metal_nut_bent_000.png` and `cable_bent_wire_001.png`
3. Decode YOLOv8 output `[1, 16, 8400]` (same as RKNN smoke test)
4. Apply NMS (IoU threshold configurable via `--iou`, default 0.45)
5. **Sort detections globally by confidence descending** so `detections[0]` is the
   real top detection regardless of class id order
6. **Validate bbox for ALL detections** (not just top 5) — pass/fail counts
   invalid bboxes across the full result set
7. **IoU gate for metal_nut_bent_000**: top detection must have IoU >= 0.7 vs
   PyTorch reference bbox `[0.8757, 0.5328, 0.1528, 0.1613]`. If class matches
   but IoU < 0.7, RESULT is FAIL.
8. For cable_bent_wire_001 (no PyTorch reference): checks expected class presence
   in top detection. A PyTorch reference can be added later for stricter gating.
9. Log per-stage latency

CLI args:
- `--conf` (default 0.25): confidence threshold
- `--iou` (default 0.45): NMS IoU threshold
- `--model` (default best.onnx): ONNX model path
- `--classes` (default phase10_classes.yaml): classes YAML path

### 3. Latency Benchmark

Expected latency on RK3588 ARM Cortex-A76/A55:

| Stage | Estimated | Notes |
|-------|-----------|-------|
| Preprocess | ~5ms | OpenCV resize + color convert |
| ONNX Inference | ~100-200ms | YOLOv8n 3M params, single core ~300ms, multi-core ~100ms |
| Postprocess | ~2ms | NMS on 8400 anchors |
| **Total** | **~110-210ms** | ~5-9 FPS |

This is significantly slower than RKNN NPU (~137ms) but provides correct output.

### 4. Integration with C++ Pipeline

If ORT smoke test passes, the C++ `localizer_worker` can be adapted:
- Link against `libonnxruntime.so` (ARM64)
- Replace RKNN inference calls with ORT `Run()` calls
- Postprocess logic (DFL decode + NMS) remains identical

This is deferred until smoke test results confirm viability.

## Deliverables

| # | Artifact | Status |
|---|----------|--------|
| 1 | `docs/experiments/phase10_onnxruntime_fallback_plan.md` | This document |
| 2 | `scripts/phase10/smoke_test_ort.py` | Created |
| 3 | Smoke test results on RK3588 | Pending (run on board) |
| 4 | Latency benchmark | Pending (run on board) |

## What This Is NOT

- This is a **CPU fallback**, not NPU/RKNN deployment
- RKNN remains the target deployment path; this is interim
- This does NOT replace the RKNN issue investigation
- Performance is expected to be 2-5x slower than RKNN NPU

## References

- `docs/experiments/phase10_rknn_fp16_diagnostic.md` — RKNN failure details
- `scripts/phase10/smoke_test_rknn.py` — Original RKNN smoke test (for comparison)
- `scripts/phase10/smoke_test_ort.py` — ORT smoke test script
