# Phase 10 v1 — airockchip YOLOv8 RKNN Re-export Plan

## Problem

Standard Ultralytics YOLOv8 ONNX (single output `[1, 16, 8400]`) produces
numerically incorrect RKNN FP16 output. DFL softmax/gather ops in the graph
are corrupted by the RKNN compiler, while box regression channels remain mostly
intact.

## Solution

Use `airockchip/ultralytics_yolov8` to export a multi-output ONNX with raw
DFL logits, then convert to RKNN FP16. DFL decode and NMS move to CPU
post-processing.

## Output Tensor Spec (9 tensors, 3 per scale)

| # | Name | Shape (640 input) | Content |
|---|------|-------------------|---------|
| 0 | output0 | `[1, 64, 80, 80]` | Box DFL logits, stride 8 |
| 1 | output1 | `[1, 12, 80, 80]` | Class scores (sigmoid), stride 8 |
| 2 | output2 | `[1, 1, 80, 80]` | Score sum, stride 8 |
| 3 | output3 | `[1, 64, 40, 40]` | Box DFL logits, stride 16 |
| 4 | output4 | `[1, 12, 40, 40]` | Class scores (sigmoid), stride 16 |
| 5 | output5 | `[1, 1, 40, 40]` | Score sum, stride 16 |
| 6 | output6 | `[1, 64, 20, 20]` | Box DFL logits, stride 32 |
| 7 | output7 | `[1, 12, 20, 20]` | Class scores (sigmoid), stride 32 |
| 8 | output8 | `[1, 1, 20, 20]` | Score sum, stride 32 |

- `64 = 4 * reg_max` (4 box sides × 16 DFL bins)
- `12 = num_classes` (metal_nut + cable, 12 defect types)
- Score sum is clamped [0,1], used in C++ for fast filtering

## Postprocess (CPU, DFL decode + NMS)

1. For each scale (stride 8/16/20):
   - Reshape box logits `[1, 64, H, W]` → `[1, 4, 16, H, W]`
   - Softmax along dim=16 (DFL bins)
   - Weighted sum: `dfl = sum(softmax * [0,1,...,15])` → `[1, 4, H, W]`
   - Decode: `x1 = (col + 0.5 - dfl_left) * stride`, etc.
2. Filter: `max_class_score >= conf_thresh`
3. NMS: per-class greedy, IoU threshold 0.45

## Steps

1. Clone `airockchip/ultralytics_yolov8` on AutoDL
2. Copy `best.pt` weights into the repo
3. Export with `format='rknn'` (triggers multi-output head)
4. Verify ONNX output tensor names/shapes/ranges
5. Convert ONNX → RKNN FP16 with rknn-toolkit2
6. Run validation: PyTorch vs ONNX vs RKNN correlation
7. Accept if class score correlation > 0.9 and top-1 class matches

## Acceptance Criteria

| Gate | Criterion |
|------|-----------|
| ONNX output count | 9 tensors |
| ONNX/PyTorch top-1 class | Must match |
| RKNN/ONNX top-1 class | Must match |
| Class score correlation | r > 0.9 per channel |
| Box center correlation | r > 0.95 per channel |
| Smoke test | 0 crashes, bbox valid, class correct |

## References

- `airockchip/ultralytics_yolov8`: modified `ultralytics/nn/modules/head.py`
- `rknn_model_zoo/examples/yolov8/python/yolov8.py`: postprocess reference
- `rknn_model_zoo/examples/yolov8/python/convert.py`: RKNN build reference
