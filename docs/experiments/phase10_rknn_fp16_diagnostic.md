# Phase 10 v1 — RKNN FP16 Diagnostic Report

## Status: BLOCKED — RKNN output mismatch

## Summary

YOLOv8n FP16 RKNN model produces **incorrect output** compared to ONNX/PyTorch.
The class score channels have near-zero correlation with the ONNX reference,
causing all detections to land at wrong positions with wrong classes.

## Evidence

### PyTorch (PASS)

```
metal_nut_bent_000.png — top detection:
  metal_nut/bent conf=0.923 norm=(0.8757, 0.5328, 0.1528, 0.1613)
  vs GT box 2: IoU=0.374
  vs GT box 1: IoU=0.841 (second detection conf=0.399)
```

### ONNX (PASS — matches PyTorch)

```
Top anchor 7275: box=(560, 341, 98, 103), score=0.923, cls=0
Output range: [0, 634.4]
```

### RKNN FP16 (FAIL)

```
Top anchor 8309: box=(322, 494, 198, 110), score=0.555, cls=3
Output range: [0, 635.0]
```

### Correlation (ONNX vs RKNN, same input image, 8400 anchors)

| Channel | Description | Correlation |
|---------|-------------|-------------|
| 0 | box_cx | 0.995 |
| 1 | box_cy | 0.996 |
| 2 | box_w | 0.699 |
| 3 | box_h | 0.651 |
| 4-15 | class scores | -0.001 to 0.81 (mostly < 0.5) |

**Box channels 0,1 are correlated. Class score channels are not.**

## Root Cause Analysis

Standard Ultralytics YOLOv8 ONNX exports a single-output graph `[1, 16, 8400]`
where DFL (Distribution Focal Loss) decode is baked into the graph. The RKNN
compiler's handling of the DFL softmax/gather ops corrupts class score channels
while leaving box regression channels mostly intact (box_cx/cy r=0.99, but
class scores r≈0).

**Attempted fix:** Use `airockchip/ultralytics_yolov8` which exports a
multi-output ONNX (9 tensors: 3 per scale) with raw DFL logits, moving DFL
decode and NMS to CPU post-processing. **This also failed** — all 9 output
tensors show near-zero correlation with ONNX reference (class scores r≈0,
box r=0.6-0.7).

**Conclusion:** rknn-toolkit2 2.3.2 has a fundamental issue with YOLOv8
detection head compilation, regardless of export format (single-output or
multi-output airockchip).

See: `docs/experiments/phase10_rknn_airockchip_reexport_plan.md`

## What Was Tried

| Attempt | Result |
|---------|--------|
| opset=20, simplify=True | RKNN rejects (opset > 19) |
| opset=19, simplify=True | Same wrong output |
| opset=12, simplify=False | Same wrong output |
| optimization_level=0 | Same wrong output |
| uint8 RGB input | Same wrong output |
| float32 /255 input | Different wrong output (scores ~0.002) |
| uint8 BGR input | Same wrong output |
| **airockchip multi-output (9 tensors)** | **Same class of failure: class r≈0, box r=0.6-0.7** |

## Environment

| Component | Version |
|-----------|---------|
| rknn-toolkit2 (PC) | 2.3.2 (bd980be9) |
| rknn-toolkit-lite2 (board) | 2.3.2 |
| librknnrt (board) | 2.3.2 (429f97ae6b) |
| NPU driver | 0.9.8 |
| Board | Orange Pi 5 (RK3588 16GB) |
| Python (PC .venv_rknn) | 3.11 |
| Python (board) | 3.10.12 |

## Artifacts

| File | SHA256 | Notes |
|------|--------|-------|
| best.pt | 36cdd96c...5a26 | PyTorch weights |
| best.onnx | c086430e...1b5 | opset=12, no simplify |
| best_fp16.rknn | e1277067...daf | opset=12, opt_level=0 |
| onnx_output.npy | — | Reference ONNX output for comparison |

## airockchip Multi-Output Correlation (Attempt 2)

| Output | Shape | ONNX range | RKNN range | r | Status |
|--------|-------|-----------|-----------|---|--------|
| box_s8 | [1,64,80,80] | [-6.5, 13.5] | [-7.1, 18.2] | 0.70 | FAIL |
| cls_s8 | [1,12,80,80] | [0.0, 0.003] | [0.002, 0.17] | 0.001 | FAIL |
| sum_s8 | [1,1,80,80] | [0.0002, 0.004] | [0.02, 0.19] | -0.02 | FAIL |
| box_s16 | [1,64,40,40] | [-5.8, 12.2] | [-3.9, 14.3] | 0.69 | FAIL |
| cls_s16 | [1,12,40,40] | [0.0, 0.92] | [0.002, 0.46] | 0.000 | FAIL |
| sum_s16 | [1,1,40,40] | [0.001, 0.93] | [0.02, 0.52] | -0.01 | FAIL |
| box_s32 | [1,64,20,20] | [-4.6, 10.1] | [-4.3, 11.7] | 0.62 | FAIL |
| cls_s32 | [1,12,20,20] | [0.0001, 0.16] | [0.002, 0.55] | -0.000 | FAIL |
| sum_s32 | [1,1,20,20] | [0.007, 0.17] | [0.02, 0.58] | 0.09 | FAIL |

## Decision Points

1. **Try rknn-toolkit2 from GitHub main branch** — may have fixes not in 2.3.2 release
2. **File issue on rknn-toolkit2 GitHub** — provide reproducible case
3. **Use ONNX runtime on RK3588 instead** — CPU inference, slower but correct
4. **Try INT8 quantization** — may avoid FP16 precision issues in class head
5. **Try YOLOv8s instead of YOLOv8n** — different head architecture may avoid the bug
6. **Defer RKNN, continue with PyTorch pipeline on PC** — focus on integration logic first
