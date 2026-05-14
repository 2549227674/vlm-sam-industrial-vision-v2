# Phase 5.1 EfficientAD-S 15 类训练结果

## 结论

- 15 类 EfficientAD-S 训练工程完成
- 15/15 ONNX 导出成功
- `convert_efficientad_rknn.py --dry-run` 显示 15/15 convertible
- 低分类别 capsule/transistor/toothbrush/hazelnut/screw 进入 targeted retrain

## 原始日志

- 完整日志：`logs/train_efficientad_full_15cls简易版.txt`
- 训练配置：20 epochs, EfficientAD-S (small), MVTec AD
- 硬件：NVIDIA GeForce RTX 4060 Laptop GPU

## AUROC 汇总表

| 类别 | image_AUROC | reference | 差距 | 级别 |
|---|---|---|---|---|
| bottle | 1.0000 | 0.983 | +0.017 | OK |
| cable | 0.9400 | 0.973 | -0.033 | P2 |
| capsule | 0.7000 | 0.988 | -0.288 | P0 |
| carpet | 0.9924 | 0.990 | +0.002 | OK |
| grid | 0.9950 | 0.985 | +0.010 | OK |
| hazelnut | 0.8675 | 0.977 | -0.110 | P1 |
| leather | 0.9769 | 0.990 | -0.013 | OK |
| metal_nut | 0.9697 | 0.979 | -0.009 | OK |
| pill | 0.9555 | 0.987 | -0.032 | OK |
| screw | 0.8920 | 0.960 | -0.068 | P1 |
| tile | 0.9978 | 0.984 | +0.014 | OK |
| toothbrush | 0.8417 | 0.983 | -0.141 | P0 |
| transistor | 0.7825 | 0.978 | -0.196 | P0 |
| wood | 0.9623 | 0.975 | -0.013 | OK |
| zipper | 0.9542 | 0.982 | -0.028 | OK |

## 风险分层

- **P0**（image_AUROC < 0.85）：capsule (0.70), transistor (0.78), toothbrush (0.84)
- **P1**（image_AUROC 0.85-0.90）：hazelnut (0.87), screw (0.89)
- **P2**（image_AUROC 0.90-0.95）：cable (0.94)

## 单独重训计划

1. 先重训 P0：capsule, transistor, toothbrush
2. 若时间允许，重训 P1：hazelnut, screw
3. P2 cable 视 P0/P1 结果决定

## 成功标准

- P0 类别优先追求 image_AUROC >= 0.90
- 若达不到，至少记录为 Stage 1 风险类，后续边缘端调低 EfficientAD threshold

## 备份

低分类别 run1 产物已备份至：
`models/efficientad_models_v2_run1_20ep_low_auroc_backup/`
（capsule, transistor, toothbrush, hazelnut, screw, cable）

## 后续验证命令

```bash
# 重训后验证
python scripts/train_efficientad.py --verify-only --categories capsule transistor toothbrush

# 重训后 RKNN 转换前置检查
python scripts/convert_efficientad_rknn.py --dry-run --categories capsule transistor toothbrush
```
