# Phase 10 v1 — YOLOv8n Training Run #1

## Summary

| Metric | Value |
|--------|-------|
| Model | YOLOv8n (3.0M params, 8.1 GFLOPs) |
| Dataset | metal_nut + cable, 12 classes, 185 images |
| Train/Val split | 126 / 59 (70/30 stratified) |
| Best epoch | 65 (early stopped at 85, patience=20) |
| Training time | ~7 minutes (RTX 4090) |
| **Best mAP50** | **0.593** |
| **Best mAP50-95** | **0.432** |

## Per-Class Results (best.pt, epoch 65)

| Class | Images | Instances | Precision | Recall | mAP50 | mAP50-95 |
|-------|--------|-----------|-----------|--------|-------|----------|
| metal_nut/bent | 8 | 9 | 0.571 | 0.667 | 0.647 | 0.437 |
| metal_nut/color | 7 | 7 | 0.640 | 0.766 | 0.830 | 0.614 |
| metal_nut/flip | 7 | 7 | 0.914 | 1.000 | 0.995 | 0.895 |
| metal_nut/scratch | 7 | 13 | 0.529 | 0.434 | 0.463 | 0.214 |
| cable/bent_wire | 4 | 4 | 0.432 | 0.500 | 0.522 | 0.310 |
| cable/cable_swap | 4 | 4 | 0.724 | 0.673 | 0.682 | 0.558 |
| cable/combined | 4 | 12 | 0.548 | 0.083 | 0.338 | 0.112 |
| cable/cut_inner_insulation | 5 | 8 | 0.662 | 0.625 | 0.540 | 0.417 |
| cable/cut_outer_insulation | 3 | 5 | 0.665 | 0.200 | 0.239 | 0.183 |
| cable/missing_cable | 4 | 4 | 0.967 | 1.000 | 0.995 | 0.833 |
| cable/missing_wire | 3 | 3 | 0.442 | 0.667 | 0.583 | 0.466 |
| cable/poke_insulation | 3 | 6 | 0.573 | 0.333 | 0.287 | 0.146 |
| **All** | **59** | **82** | **0.639** | **0.579** | **0.593** | **0.432** |

## Analysis

### Strong Classes (mAP50 > 0.6)
- **metal_nut/flip** (0.995): Near-perfect detection. Flip defects are visually distinctive.
- **cable/missing_cable** (0.995): Near-perfect. Missing cable is a large, obvious defect.
- **metal_nut/color** (0.830): Good. Color defects are visually distinct.
- **cable/cable_swap** (0.682): Moderate. Cable swap has clear visual pattern.

### Weak Classes (mAP50 < 0.4)
- **cable/cut_outer_insulation** (0.239): Very low recall (0.20). Small, subtle defect.
- **cable/poke_insulation** (0.287): Low recall (0.333). Small puncture marks.
- **cable/combined** (0.338): Very low recall (0.083). Multiple overlapping defects confuse detector.
- **metal_nut/scratch** (0.463): Moderate. Scratches can be thin and subtle.

### Root Causes for Weak Classes
1. **Small instances**: cut_outer_insulation, poke_insulation are small relative to image size.
2. **Low sample count**: 3-4 val images per class limits evaluation reliability.
3. **Visual subtlety**: Some defects (scratches, small cuts) are hard to distinguish from background.
4. **Class confusion**: combined defects overlap with individual defect types.

## Training Hyperparameters

```yaml
model: yolov8n.pt
imgsz: 640
epochs: 100 (stopped at 85)
batch: 16
patience: 20
optimizer: auto (SGD)
lr0: 0.01
seed: 42
augmentation:
  hsv_h: 0.015
  hsv_s: 0.7
  hsv_v: 0.4
  degrees: 5.0
  translate: 0.1
  scale: 0.3
  shear: 2.0
  fliplr: 0.5
  mosaic: 1.0
```

## Inference Speed

| Stage | Time |
|-------|------|
| Preprocess | 0.1 ms |
| Inference | 0.3 ms |
| Postprocess | 0.4 ms |
| **Total** | **0.8 ms** (~1250 FPS) |

## Artifacts

### PyTorch Weights (best.pt)

| Property | Value |
|----------|-------|
| Local path | `models/yolov8n_phase10/yolov8n_metal_nut_cable_best.pt` |
| AutoDL path | `/root/vlm-sam-industrial-vision-v2/runs/detect/runs/phase10/yolov8n_metal_nut_cable/weights/best.pt` |
| Size | 6,258,474 bytes (6.3 MB) |
| SHA256 | `36cdd96cf4b71422eebc2ff37f43955efd37744f702f15e653db596523455a26` |
| Git status | NOT tracked (under `/models/` gitignore) |

**Retrieve from AutoDL:**
```bash
rsync -avz autodl-phase10:/root/vlm-sam-industrial-vision-v2/runs/detect/runs/phase10/yolov8n_metal_nut_cable/weights/best.pt \
  models/yolov8n_phase10/yolov8n_metal_nut_cable_best.pt
```

> **Security note:** `autodl-phase10` is an SSH host alias configured in `~/.ssh/config`.
> Never commit passwords, tokens, private keys, host-specific credentials, or `sshpass` commands to the repository.

### Other Artifacts

| File | Local path | Notes |
|------|-----------|-------|
| Results CSV | `models/yolov8n_phase10/results.csv` | Per-epoch metrics |
| Remote log | `/root/autodl-tmp/yolov8n_phase10_train.log` | Full training output |
| Remote runs dir | `runs/detect/runs/phase10/yolov8n_metal_nut_cable/` | Ultralytics run artifacts |

### ONNX Export

| Property | Value |
|----------|-------|
| Local path | `models/yolov8n_phase10/yolov8n_metal_nut_cable_best.onnx` |
| Size | 12,274,111 bytes (11.7 MB) |
| SHA256 | `731ca448252eb9613072d16e0efac2fc84bef02e8d5aef8fa63fd525052d1cd3` |
| Opset | 20 |
| Input | `images` — shape `[1, 3, 640, 640]` BCHW |
| Output | `output0` — shape `[1, 16, 8400]` |
| ONNX check | PASS |
| Git status | NOT tracked (under `/models/` gitignore) |

**Export command:**
```bash
yolo export model=models/yolov8n_phase10/yolov8n_metal_nut_cable_best.pt format=onnx imgsz=640 simplify=True
```

**Verify command:**
```bash
python -c "import onnx; m=onnx.load('models/yolov8n_phase10/yolov8n_metal_nut_cable_best.onnx'); onnx.checker.check_model(m); print('PASS')"
```

## Next Steps

1. **Per-class threshold tuning**: Current default conf=0.25 may not be optimal for weak classes.
2. **Data augmentation review**: Consider adding more aggressive augmentation for small defects.
3. **Export to RKNN**: Convert best.pt → ONNX → RKNN for edge deployment.
4. **Integration with edge pipeline**: Replace FastSAM bbox with YOLOv8n detection.
