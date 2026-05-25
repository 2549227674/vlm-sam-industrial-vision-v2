# Phase 10 v1 — RKNN Issue Reproduction Guide

## Status: BLOCKED — rknn-toolkit2 YOLOv8 detection head numerical corruption

## Summary

rknn-toolkit2 2.3.2 produces numerically incorrect output when compiling YOLOv8
detection head ONNX models. Class score channels have near-zero correlation with
ONNX reference, while box regression channels remain mostly intact. This affects
both single-output (Ultralytics) and multi-output (airockchip) export formats.

## Environment

| Component | Version | Notes |
|-----------|---------|-------|
| rknn-toolkit2 (PC) | 2.3.2 (bd980be9) | `pip show rknn-toolkit2` |
| rknn-toolkit-lite2 (board) | 2.3.2 | `pip show rknn-toolkit-lite2` |
| librknnrt (board) | 2.3.2 (429f97ae6b) | `/usr/lib/librknnrt.so` |
| NPU driver | 0.9.8 | `dmesg | grep rknpu` |
| Board | Orange Pi 5 (RK3588 16GB) | Kernel 6.1.99-rockchip-rk3588 |
| Python (PC) | 3.11 | `.venv_rknn` |
| Python (board) | 3.10.12 | System python3 |
| PyTorch | 2.x (Ultralytics) | Training reference |
| ONNX Runtime | 1.x | Correctness reference |

## Model Artifacts (SHA256 only, binaries NOT committed)

### Standard Ultralytics Export

| Artifact | SHA256 | Path (local) |
|----------|--------|--------------|
| PyTorch best.pt | `36cdd96cf4b71422eebc2ff37f43955efd37744f702f15e653db596523455a26` | `models/yolov8n_phase10/yolov8n_metal_nut_cable_best.pt` |
| ONNX (opset=19, simplify) | `fe4bfe523fb4476adb9aee344fb930e1de4d2e0988112ea4d096a6113846e72e` | `models/yolov8n_phase10/yolov8n_metal_nut_cable_best.onnx` |
| RKNN FP16 (opt_level=0) | `2ecbf5d92cb081f188dbd4e43d5be5f3d83545d2dc172066a8e8fa8be553c95a` | `models/yolov8n_phase10/yolov8n_metal_nut_cable_best_fp16.rknn` |

**Standard ONNX spec:**
- Input: `images` — `[1, 3, 640, 640]` float32 BCHW
- Output: `output0` — `[1, 16, 8400]` float32
  - Channels 0-3: box (cx, cy, w, h) in pixel coords
  - Channels 4-15: class scores (12 classes, sigmoid)

### airockchip Multi-Output Export

| Artifact | SHA256 | Path (local) |
|----------|--------|--------------|
| ONNX (airockchip) | `0c49a84633d40a4d1764ebd0e43fa8be78f2dc285845086f6ba21dfb1696678e` | `models/yolov8n_phase10/yolov8n_metal_nut_cable_best_airockchip.onnx` |
| RKNN FP16 (airockchip) | `ad169972d1c8c0e8fdfaaa8dd10359dab6cf5193e6cc69488fe4399d3ef4aefb` | `models/yolov8n_phase10/yolov8n_metal_nut_cable_best_airockchip_fp16.rknn` |

**airockchip ONNX spec (9 tensors):**

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

## Correlation Table (ONNX vs RKNN, metal_nut_bent_000.png)

### Standard Single-Output

| Channel | Description | Pearson r | Status |
|---------|-------------|-----------|--------|
| 0 | box_cx | 0.995 | PASS |
| 1 | box_cy | 0.996 | PASS |
| 2 | box_w | 0.699 | FAIL |
| 3 | box_h | 0.651 | FAIL |
| 4 | class 0 (bent) | ~0.0 | FAIL |
| 5 | class 1 (color) | ~0.0 | FAIL |
| ... | ... | ... | FAIL |
| 15 | class 11 | ~0.0 | FAIL |

### airockchip Multi-Output

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

## What Was Tried

| # | Attempt | Result |
|---|---------|--------|
| 1 | opset=20, simplify=True | RKNN rejects (opset > 19) |
| 2 | opset=19, simplify=True | Same wrong output |
| 3 | opset=12, simplify=False | Same wrong output |
| 4 | optimization_level=0 | Same wrong output |
| 5 | uint8 RGB input | Same wrong output |
| 6 | float32 /255 input | Different wrong output (scores ~0.002) |
| 7 | uint8 BGR input | Same wrong output |
| 8 | airockchip multi-output (9 tensors) | Same class of failure |

## Test Image

One test image is available at:
`datasets/phase10/images/val/metal_nut_bent_000.png`

PyTorch reference output:
```
Top detection: metal_nut/bent conf=0.923 bbox_norm=[0.8757, 0.5328, 0.1528, 0.1613]
```

## Minimal Reproduction Steps

### Step 1: Environment Setup

```bash
# Create venv with rknn-toolkit2
python3.11 -m venv .venv_rknn
source .venv_rknn/bin/activate
pip install rknn-toolkit2==2.3.2
pip install onnxruntime opencv-python-headless numpy
```

### Step 2: Get Model Files

```bash
# best.pt — retrieve from training run (AutoDL)
rsync -avz autodl-phase10:/root/vlm-sam-industrial-vision-v2/runs/detect/runs/phase10/yolov8n_metal_nut_cable/weights/best.pt \
  models/yolov8n_phase10/yolov8n_metal_nut_cable_best.pt

# Verify SHA256
sha256sum models/yolov8n_phase10/yolov8n_metal_nut_cable_best.pt
# Expected: 36cdd96cf4b71422eebc2ff37f43955efd37744f702f15e653db596523455a26
```

### Step 3: Export ONNX (standard)

```bash
yolo export \
  model=models/yolov8n_phase10/yolov8n_metal_nut_cable_best.pt \
  format=onnx imgsz=640 simplify=True opset=19
```

### Step 4: Convert to RKNN FP16

```python
from rknn.api import RKNN

rknn = RKNN(verbose=False)
rknn.config(
    target_platform="rk3588",
    mean_values=[[0, 0, 0]],
    std_values=[[255, 255, 255]],
    optimization_level=0,
)
rknn.load_onnx(model="models/yolov8n_phase10/yolov8n_metal_nut_cable_best.onnx")
rknn.build(do_quantization=False)
rknn.export_rknn("models/yolov8n_phase10/yolov8n_metal_nut_cable_best_fp16.rknn")
rknn.release()
```

### Step 5: Compare Outputs

```python
import numpy as np
import onnxruntime as ort
from rknnlite.api import RKNNLite

# Load test image, preprocess (letterbox 640, BGR->RGB, /255, CHW)
img = ...  # shape [1, 3, 640, 640] float32

# ONNX reference
sess = ort.InferenceSession("models/yolov8n_phase10/yolov8n_metal_nut_cable_best.onnx")
onnx_out = sess.run(None, {"images": img})[0]  # [1, 16, 8400]

# RKNN
rknn = RKNNLite()
rknn.load_rknn("models/yolov8n_phase10/yolov8n_metal_nut_cable_best_fp16.rknn")
rknn.init_runtime()
rknn_out = rknn.inference(inputs=[(img * 255).astype(np.uint8)])[0]  # [1, 16, 8400]

# Correlation per channel
for ch in range(16):
    r = np.corrcoef(onnx_out[0, ch, :].flatten(), rknn_out[0, ch, :].flatten())[0, 1]
    print(f"Channel {ch}: r={r:.4f}")
```

Expected: box channels 0-1 have r>0.99, class channels 4-15 have r≈0 (the bug).

## Root Cause Hypothesis

The RKNN compiler's handling of DFL (Distribution Focal Loss) softmax/gather
operations in the YOLOv8 detection head corrupts class score channels while
leaving box regression channels mostly intact. This happens regardless of:
- Export format (single-output or multi-output airockchip)
- Opset version (12 or 19)
- Optimization level (0-3)
- Input format (uint8/float32, RGB/BGR)

The corruption pattern suggests an issue in how the RKNN compiler partitions or
schedules the attention-like operations in the DFL decode path.

## Suggested Investigation

1. **Layer-by-layer accuracy analysis**: Use `rknn.accuracy_analysis()` to find
   the first layer where ONNX and RKNN outputs diverge.

2. **Simplify the graph**: Try removing DFL from the ONNX export (export raw
   logits without softmax/gather) and see if RKNN handles the rest correctly.

3. **Test with RKNN Model Zoo**: Check if the official `rknn_model_zoo` YOLOv8
   example has the same issue with a fresh model.

4. **Try rknn-toolkit2 from GitHub main**: May contain fixes not in 2.3.2 release.

## Contact

This issue affects rknn-toolkit2 2.3.2 on RK3588. If you can reproduce, please
file at: https://github.com/airockchip/rknn-toolkit2/issues
