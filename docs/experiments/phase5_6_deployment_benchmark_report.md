# Phase 5.6 Deployment Benchmark Report

## 1. 实验目的

在 PC 端（RTX 4090 48GB, fp16）评估四变体在全 15 类 MVTec AD 上的缺陷检测能力，
为 RK3588 部署选型提供数据依据。

四变体按 **模型尺寸 × 微调模式** 2×2 矩阵组合：

| 变体 | 模型 | 模式 | Prompt |
|------|------|------|--------|
| `2B_base` | Qwen3-VL-2B | 基座 fp16 | 工程化 (~300 tokens) |
| `2B_lora` | Qwen3-VL-2B | LoRA fp16 | 极简 (~50 tokens) |
| `4B_base` | Qwen3-VL-4B | 基座 fp16 | 工程化 (~300 tokens) |
| `4B_lora` | Qwen3-VL-4B | LoRA fp16 | 极简 (~50 tokens) |

## 2. 实验口径

- **主实验**：`max_tokens=200`, greedy decoding (`do_sample=False`), eval=409 samples (15 类 × 70/30 split)
- **评估脚本**：`scripts/eval_ab_test.py --mode deployment`
- **GT 来源**：`scripts/mvtec_mask_to_json.py` 自动生成（基于 MVTec 官方 GT mask）
- **训练配置**：LoRA rank=32, alpha=32, target=q_proj/k_proj/v_proj/o_proj, 5 epochs, cosine scheduler

## 3. 四变体主结果（max_tokens=200）

| 变体 | JSON OK | Cat Exact | DefType Exact | BBox IoU≥0.5 | Avg Prompt Tok | Avg Output Tok |
|------|---------|-----------|---------------|--------------|----------------|----------------|
| 2B_base | 96.1% (393/409) | 53.1% (217/409) | 11.2% (46/409) | 1.5% (6/409) | 1156 | 119 |
| 2B_lora | 95.6% (391/409) | 94.4% (386/409) | 53.1% (217/409) | 48.9% (200/409) | 958 | 110 |
| 4B_base | 98.0% (401/409) | 59.2% (242/409) | 10.5% (43/409) | 0.0% (0/409) | 1156 | 114 |
| 4B_lora | 95.8% (392/409) | 95.8% (392/409) | 64.8% (265/409) | 64.5% (264/409) | 958 | 114 |

> 完整 per-category 数据见：`logs/ab_eval_report_v2_deployment_2b.json`、`logs/ab_eval_report_v2_deployment_4b.json`
> Per-sample 详情见：`results/ab_eval_predictions_{size}_{variant}_deployment.jsonl`

## 4. Defect Group Exact（辅助分析指标）

基于 alias 分组的粗粒度精确率（132 个适用样本，覆盖 screw/zipper/cable/capsule/pill/carpet）：

| 变体 | defect_type_exact | defect_group_exact | Delta |
|------|-------------------|--------------------|-------|
| 2B_base | 11.2% | 28.0% | +16.8% |
| 2B_lora | 53.1% | 67.4% | +14.4% |
| 4B_base | 10.5% | 21.2% | +10.7% |
| 4B_lora | 64.8% | 77.3% | +12.5% |

> 完整分析见：`results/defect_group_analysis.md`
>
> **注意**：defect_group_exact 是辅助分析指标，不替代 strict defect_type_exact。
> 它反映模型是否学会"大类方向"（如区分 wire_defect vs insulation_defect），
> 但不能衡量精确子类型识别能力。

## 5. 关键发现

### 5a. LoRA 是决定性因素，不是单纯模型尺寸

4B_base 在 defect_type_exact 上仅 10.5%，甚至低于 2B_base 的 11.2%。
但 4B_lora 达到 64.8%，2B_lora 为 53.1%。
LoRA 微调带来的 category_exact 提升幅度（53%→94% / 59%→96%）远超模型尺寸从 2B→4B 的提升。

### 5b. 4B_base BBox=0 说明 base 模型无工业 bbox 对齐能力

4B_base 的 bbox_iou_at_0_5 为 0.0%（0/409），2B_base 仅 1.5%（6/409）。
基座模型虽然能输出格式正确的 JSON，但 bbox 坐标完全不对齐。
LoRA 微调后 BBox 大幅提升（2B_lora 48.9%, 4B_lora 64.5%），
说明 LoRA 不仅改善了 defect_type 分类，还显著提升了空间定位能力。

### 5c. JSON 失败主要来自 200-token 截断

四变体 JSON OK 均 >95%，剩余失败主要集中在：
- grid（2B_base 75%, 2B_lora 70%, 4B_lora 80%）
- wood（2B_base 75%, 2B_lora 75%, 4B_lora 80%）
- toothbrush（2B_lora 66.7%）

这些类别的 defect 描述较长，output_tokens 达到 200 上限时 JSON 被截断。
截断样本详情见：`scripts/truncated_2b_lora.txt`（18 个）、`scripts/truncated_4b_lora.txt`（17 个）。

### 5d. defect_type_exact 受 MVTec 目录名标签和 GT 自动生成方式影响

GT 的 defect_type 直接取自 MVTec 目录名（如 `scratch_head`、`fabric_border`），
由 `scripts/mvtec_mask_to_json.py` 自动生成。
部分目录名语义模糊（如 `combined`、`good`），且不同类别下相同目录名含义不同。
模型预测的 defect_type 可能语义正确但与目录名不完全匹配（如预测 `scratch` vs GT `scratch_head`）。
这解释了 defect_type_exact 与 defect_group_exact 之间存在 10-17pp 差距。

### 5e. 4B_lora 优势集中在复杂类别

4B_lora 相比 2B_lora 的主要优势类别：

| 类别 | 2B_lora DefType | 4B_lora DefType | Delta |
|------|-----------------|-----------------|-------|
| screw | 31.6% | 57.9% | +26.3% |
| zipper | 41.0% | 56.4% | +15.4% |
| grid | 25.0% | 60.0% | +35.0% |
| transistor | 25.0% | 50.0% | +25.0% |
| wood | 45.0% | 65.0% | +20.0% |
| hazelnut | 58.3% | 79.2% | +20.9% |

这些类别 defect_type 子类多（screw 有 5 种、zipper 有 7 种、grid 有 5 种），
4B 模型在区分相似子类型上优势明显。

## 6. max_tokens=300 截断敏感性补测

**性质**：截断敏感性补测，不替代 `max_tokens=200` 主实验结果。

**方法**：用 `--image-filter scripts/truncated_2b_lora.txt` 重跑被截断样本，
`max_tokens=300`。

**结果**（仅截断子集，2B: 26 samples, 4B: 25 samples）：

| 变体 | JSON OK | Cat Exact | DefType Exact | BBox IoU≥0.5 |
|------|---------|-----------|---------------|--------------|
| 2B_base | 80.8% | 38.5% | 19.2% | 0.0% |
| 2B_lora | 65.4% | 65.4% | 34.6% | 50.0% |
| 4B_base | 100.0% | 68.0% | 20.0% | 0.0% |
| 4B_lora | 68.0% | 68.0% | 40.0% | 56.0% |

**局限性**：`--image-filter` 按 basename 匹配，不同 category 下同名文件（如 `scratch_000.png`）
可能被误纳入。子集样本量小（25-26），百分比波动大。结果仅作辅助说明。

> 完整数据见：`results/phase5_6_deployment/max-token-300/`

## 7. 数据与 GT 局限性

1. **defect_type 来自目录名**：MVTec AD 的缺陷子目录名直接作为 GT defect_type，
   部分目录名语义模糊（如 `combined` 表示多种缺陷共存、`good` 在 test 集中表示无缺陷）

2. **bbox 来自 mask 外接框**：GT bbox 由 `connectedComponentsWithStats` 从 GT mask 提取外接矩形，
   不是人工标注的 tight bbox，存在边界不精确的问题

3. **severity/confidence 为伪 GT**：severity 和 confidence 由脚本根据缺陷面积自动推算，
   不是人工标注，仅用于 schema 格式验证，不作为精度评估依据

4. **combined 类别有歧义**：`combined` 类别包含多种缺陷类型的组合，
   模型预测的单一 defect_type 无法完全匹配 GT 的复合语义

## 8. 后续实验

**Phase 5.7 Method Control Benchmark** ✅ 已完成

base + 极简 prompt vs LoRA + 极简 prompt，消除 prompt 差异，隔离 LoRA 微调的真实收益。

结论：LoRA-SFT 净贡献显著，Phase 5.6 中 LoRA 的优势不是 prompt 工程假象。详见：`docs/experiments/phase5_7_method_control_benchmark_report.md`

**Phase 5.8 OPRO Prompt-only Baseline**（可选 / 进行中）

量化 prompt engineering 的单独贡献上界。轻量版建议只跑 2B：

```bash
CUDA_VISIBLE_DEVICES=0 python scripts/optimize_prompt_opro.py \
    --model-size 2B --num-iterations 3 --num-candidates 5 \
    | tee logs/opro_2b.log
```

产出：`results/prompt_opro_best.json`。如执行完成，报告写入 `docs/experiments/phase5_8_opro_baseline_report.md`。

## 附录：文件索引

```
results/phase5_6_deployment/
├── reports/
│   ├── ab_eval_report_v2_deployment_2b_main.json    # 2B 主实验聚合报告
│   ├── ab_eval_report_v2_deployment_4b_main.json    # 4B 主实验聚合报告
│   └── ...
├── predictions/
│   ├── ab_eval_predictions_2B_2B_base_deployment.jsonl
│   ├── ab_eval_predictions_2B_2B_lora_deployment.jsonl
│   ├── ab_eval_predictions_4B_4B_base_deployment.jsonl
│   └── ab_eval_predictions_4B_4B_lora_deployment.jsonl
├── analysis/
│   ├── lora_diff_analysis.md                        # 2B_lora vs 4B_lora 逐样本差异
│   └── defect_group_analysis.md                     # defect group alias 分析
└── max-token-300/                                   # 截断敏感性补测
    ├── ab_eval_report_v2_deployment_2B_maxtoken_300.json
    ├── ab_eval_report_v2_deployment_4B__maxtoken_300.json
    └── ab_eval_predictions_*__maxtoken_300.jsonl
```
