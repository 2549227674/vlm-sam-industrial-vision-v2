# Phase 5.1 EfficientAD-S 15 类训练结果

## 结论

- 15 类 EfficientAD-S 训练工程完成
- 15/15 ONNX 导出成功
- `convert_efficientad_rknn.py --dry-run` 显示 15/15 convertible
- **P0 处理完成**：
  - capsule：image_AUROC=0.70（系统性弱点，接受基线，采用自适应低阈值策略）
  - transistor：40ep 后 image_AUROC=0.90，已采用 ✅
  - toothbrush：40ep 后 image_AUROC=0.91，已采用 ✅
- **P1 待处理**：hazelnut(0.87), screw(0.89) — 计划运行 40ep
- **P2 可选**：cable(0.94) — 视时间决定

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

## capsule 专项分析

### 问题诊断

capsule 是本项目 EfficientAD-S 训练中的系统性弱点类别：

| 实验 | image_AUROC | pixel_AUROC | 结论 |
|---|---|---|---|
| 20ep (seed=42) | 0.7000 | 0.8788 | 基线，采用 |
| 40ep (seed=42) | 0.6741 | 0.9345 | image 下降，不采用 |
| 当前生产版本 | **0.7000** | 0.8788 | 已恢复 20ep |

**关键发现**：pixel_AUROC（局部缺陷定位，0.88）显著高于 image_AUROC（整图异常排序，0.70）。
这说明 EfficientAD-S 的特征提取对 capsule 的局部纹理异常有一定感知能力，
但整图级别的异常程度排序能力弱——属于模型在该类别的**结构性弱点**，
单纯增加 epoch 或调整 seed 不能根本解决。

40ep 导致 image_AUROC 下降而 pixel_AUROC 上升，符合"过拟合到局部特征"的模式。

### 后续实验计划

仅做一次 seed 变体实验作为止损尝试：

```bash
# 实验命令（需手动运行，不在此处执行）
python scripts/train_efficientad.py --categories capsule --epochs 40
# 运行前先将脚本内 pl.seed_everything(42) 临时改为 pl.seed_everything(123)
# 产物保存到独立目录避免覆盖：
# 手动 mv models/efficientad_models/capsule/ models/efficientad_models/capsule_seed123_40ep/
# 再从备份恢复 20ep 版本
```

**止损条件**：若 seed=123 + 40ep 的 image_AUROC ≤ 0.75，终止 capsule 重训实验，
接受 0.70 基线，改用阈值策略（见 edge/config.yaml 更新）。

### 部署策略

capsule 采用**类别级自适应阈值**：
- 降低 Stage 1 触发阈值，用高召回换低漏检
- 偶发的正常图误触发 FastSAM+VLM 可接受（VLM 会输出"无缺陷"自然过滤）
- 具体配置见 `edge/config.yaml` 的 `per_category_threshold` 字段

### 工程叙事价值

此发现可在简历/面试中这样描述：
> "识别了 EfficientAD-S 在 capsule 类别的系统性精度短板（image_AUROC=0.70 vs
> pixel_AUROC=0.88 的分裂现象），判断根因为整图异常排序能力弱而非局部定位失效，
> 采用类别级自适应阈值策略（capsule 阈值=0.30，其余类默认=0.50），
> 以高召回换低漏检，在不重新设计模型架构的前提下完成工程 workaround。"
