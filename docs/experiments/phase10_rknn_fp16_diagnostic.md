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

The RKNN compiler (rknn-toolkit2 2.3.2) appears to mishandle the YOLOv8
detection head. The class score branch produces values ~10x higher than ONNX
and at completely different anchor positions.

Possible causes:
1. FP16 precision loss in the class head's sigmoid/split operations
2. Op fusion bug in the RKNN compiler for YOLOv8's specific head architecture
3. Output tensor reordering by the RKNN runtime

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

## Decision Points

1. **Try rknn-toolkit2 from GitHub main branch** — may have fixes not in 2.3.2 release
2. **Try rknn_model_zoo YOLOv8 example** — airockchip may have a working conversion recipe
3. **File issue on rknn-toolkit2 GitHub** — provide reproducible case
4. **Use ONNX runtime on RK3588 instead** — CPU inference, slower but correct
5. **Defer RKNN, continue with PyTorch pipeline on PC** — focus on integration logic first
6. **Try YOLOv8s instead of YOLOv8n** — different head architecture may avoid the bug
