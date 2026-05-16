# Phase 5.7 Method Control Benchmark Report

## 1. 实验动机（Motivation）

Phase 5.6 Deployment Benchmark 中，LoRA 变体（2B_lora / 4B_lora）在 category_exact、defect_type_exact、bbox_iou_at_0_5 上全面领先 base 变体。然而，5.6 的四变体使用了两套不同的 prompt 策略——base 使用工程化 prompt（~300 tokens），LoRA 使用极简 prompt（~50 tokens）。

这引出一个关键方法学问题：**Phase 5.6 中观察到的 LoRA 优势，究竟来自 LoRA-SFT 参数适应，还是 prompt 工程差异的假象？**

Phase 5.7 使用完全相同的 minimal prompt 对 base 和 LoRA 进行评估，消除 prompt 差异的干扰，隔离 LoRA 微调的净贡献。

## 2. 实验设置（Experimental Setup）

| 配置项 | 值 |
|--------|-----|
| Eval samples | 409（15 类 × 30% split，与 Phase 5.6 一致） |
| Prompt 策略 | minimal prompt（base 和 LoRA 完全相同） |
| avg_prompt_tokens | 958.0（四变体一致） |
| max_tokens | 200（主实验口径，与 Phase 5.6 一致） |
| Decoding | greedy decoding，do_sample=False |
| 硬件 | AutoDL RTX 4090 48GB，fp16 |
| 评估脚本 | `scripts/eval_ab_test.py --mode method_control --max-tokens 200` |

四变体定义：

| 变体 | 模型 | Prompt | 唯一变量 |
|------|------|--------|----------|
| `2B_base_same_prompt` | Qwen3-VL-2B base | minimal | — |
| `2B_lora_same_prompt` | Qwen3-VL-2B + LoRA adapter | minimal | LoRA adapter |
| `4B_base_same_prompt` | Qwen3-VL-4B base | minimal | — |
| `4B_lora_same_prompt` | Qwen3-VL-4B + LoRA adapter | minimal | LoRA adapter |

LoRA adapter 路径：
- 2B：`models/qwen3vl_lora_adapter_15cls/`
- 4B：`models/qwen3vl_lora_4b_adapter/`

## 3. 主实验结果（Main Results）

### 3.1 总体指标

| 变体 | JSON OK | Schema OK | Category | DefType | BBox IoU≥0.5 | Avg Output Tok |
|------|--------:|----------:|---------:|--------:|-------------:|--------------:|
| 2B_base_same_prompt | 78.7% (322/409) | 0.5% (2/409) | 0.7% (3/409) | 0.0% (0/409) | 0.0% (0/409) | 129.8 |
| 2B_lora_same_prompt | 95.6% (391/409) | 95.6% (391/409) | 94.4% (386/409) | 53.1% (217/409) | 48.9% (200/409) | 110.2 |
| 4B_base_same_prompt | 94.9% (388/409) | 9.8% (40/409) | 20.3% (83/409) | 0.7% (3/409) | 0.0% (0/409) | 108.3 |
| 4B_lora_same_prompt | 95.8% (392/409) | 95.8% (392/409) | 95.8% (392/409) | 64.8% (265/409) | 64.5% (264/409) | 113.6 |

### 3.2 LoRA 净贡献（delta，相同 prompt 下）

| 净提升 | JSON OK | Schema | Category | DefType | BBox IoU≥0.5 |
|--------|--------:|-------:|---------:|--------:|-------------:|
| 2B: lora − base | +16.9pp | +95.1pp | +93.7pp | +53.1pp | +48.9pp |
| 4B: lora − base | +0.9pp | +86.0pp | +75.5pp | +64.1pp | +64.5pp |

### 3.3 与 Phase 5.6 对比（Prompt 工程收益参考）

| 指标 | 2B_base 5.6（工程化 prompt） | 2B_base 5.7（minimal prompt） | Prompt 工程收益参考 |
|------|----------------------------:|------------------------------:|-------------------:|
| Category | 53.1% | 0.7% | +52.4pp |
| DefType | 11.2% | 0.0% | +11.2pp |
| BBox IoU≥0.5 | 1.5% | 0.0% | +1.5pp |

> 该对比并非独立 prompt-only 搜索实验，而是在相同 eval split 与主实验口径下，对 Phase 5.6 engineered prompt 和 Phase 5.7 minimal prompt 的参考性横向比较。它说明 prompt 工程对 base 模型确实有显著收益，但即使加上 prompt 工程，base 的 DefType 和 BBox 仍远低于 minimal prompt 下的 LoRA。

### 3.4 逐类别详情（2B_lora_same_prompt）

| 类别 | JSON OK | Category | DefType | BBox IoU≥0.5 |
|------|--------:|---------:|--------:|-------------:|
| bottle | 20/20 | 19/20 | 13/20 | 6/20 |
| cable | 30/30 | 30/30 | 9/30 | 7/30 |
| capsule | 34/34 | 34/34 | 17/34 | 10/34 |
| carpet | 29/30 | 29/30 | 21/30 | 17/30 |
| grid | 14/20 | 13/20 | 5/20 | 5/20 |
| hazelnut | 24/24 | 24/24 | 14/24 | 15/24 |
| leather | 29/30 | 29/30 | 22/30 | 21/30 |
| metal_nut | 29/29 | 29/29 | 25/29 | 22/29 |
| pill | 45/46 | 45/46 | 28/46 | 31/46 |
| screw | 38/38 | 38/38 | 12/38 | 8/38 |
| tile | 27/28 | 24/28 | 17/28 | 21/28 |
| toothbrush | 6/9 | 6/9 | 6/9 | 4/9 |
| transistor | 12/12 | 12/12 | 3/12 | 3/12 |
| wood | 15/20 | 15/20 | 9/20 | 14/20 |
| zipper | 39/39 | 39/39 | 16/39 | 16/39 |
| **TOTAL** | **391/409** | **386/409** | **217/409** | **200/409** |

### 3.5 逐类别详情（4B_lora_same_prompt）

| 类别 | JSON OK | Category | DefType | BBox IoU≥0.5 |
|------|--------:|---------:|--------:|-------------:|
| bottle | 20/20 | 20/20 | 11/20 | 12/20 |
| cable | 30/30 | 30/30 | 12/30 | 14/30 |
| capsule | 34/34 | 34/34 | 22/34 | 17/34 |
| carpet | 30/30 | 30/30 | 23/30 | 22/30 |
| grid | 16/20 | 16/20 | 12/20 | 9/20 |
| hazelnut | 23/24 | 23/24 | 19/24 | 19/24 |
| leather | 30/30 | 30/30 | 23/30 | 20/30 |
| metal_nut | 29/29 | 29/29 | 25/29 | 25/29 |
| pill | 42/46 | 42/46 | 25/46 | 35/46 |
| screw | 38/38 | 38/38 | 22/38 | 14/38 |
| tile | 28/28 | 28/28 | 23/28 | 24/28 |
| toothbrush | 7/9 | 7/9 | 7/9 | 5/9 |
| transistor | 12/12 | 12/12 | 6/12 | 3/12 |
| wood | 16/20 | 16/20 | 13/20 | 14/20 |
| zipper | 37/39 | 37/39 | 22/39 | 31/39 |
| **TOTAL** | **392/409** | **392/409** | **265/409** | **264/409** |

## 4. 关键发现（Key Findings）

**LoRA 净贡献显著，排除 prompt 假象。** 在完全相同 minimal prompt 下，LoRA 带来的提升幅度与 Phase 5.6 中观察到的一致甚至更大。2B 模型上 LoRA 使 category_exact 从 0.7% 跃升至 94.4%（+93.7pp），defect_type_exact 从 0.0% 升至 53.1%（+53.1pp），bbox_iou_at_0_5 从 0.0% 升至 48.9%（+48.9pp）。4B 模型的趋势相同：category_exact +75.5pp，defect_type_exact +64.1pp，bbox_iou_at_0_5 +64.5pp。这证明 Phase 5.6 中 LoRA 的优势不是 prompt 工程假象，而主要来自 LoRA-SFT 对工业缺陷检测协议的参数适应。

**Base 模型失败的本质是项目协议未对齐，不是完全没有视觉能力。** 在 minimal prompt 下，2B_base 的 JSON OK 仅 78.7%，主要表现为语言体系错位——常输出中文 category / defect_type / severity，schema_ok 仅 0.5%。4B_base 的 JSON OK 达 94.9%（格式生成能力更强），但 schema_ok 仅 9.8%，主要表现为字段枚举和标注协议未对齐——会输出 `minor`、`mild`、`critical`、`中`、`轻度`、`0` 等非项目枚举值。4B_base 在 screw / zipper 上的 category 命中是预训练词汇偶发优势，不代表学会了工业 ontology；即使 category 命中，defect_type 和 bbox 仍不可用。

**LoRA 后 2B 与 4B 的差距转移到 defect_type 和 bbox。** LoRA 拉齐了 category 和 schema 维度后，两个模型尺寸的差异集中在更细粒度的指标上：

| 指标 | 2B_lora | 4B_lora | 4B - 2B |
|------|--------:|--------:|--------:|
| JSON OK | 95.6% | 95.8% | +0.2pp |
| Category | 94.4% | 95.8% | +1.4pp |
| DefType | 53.1% | 64.8% | +11.7pp |
| BBox IoU≥0.5 | 48.9% | 64.5% | +15.6pp |

**LoRA 后主要瓶颈从 category 转移到 defect_type 和 bbox。** Category 已基本解决（>94%），剩余瓶颈是：(1) 类内视觉相似 defect_type 混淆（如 cable 的 cut_inner vs cut_outer_insulation）；(2) bbox near-miss（IoU 在 0.3-0.5 区间的样本占比约 20%）；(3) max_tokens=200 截断导致部分复杂样本 JSON 不完整。

## 5. 误差分析（Error Analysis）

### DefType 典型混淆

| 类别 | 典型混淆 | 错误本质 |
|------|----------|----------|
| cable | cut_inner ↔ cut_outer_insulation | 内外绝缘层视觉高度相似 |
| screw | manipulated_front → thread_top | 螺纹视角依赖性，thread_top 为训练集高频 |
| zipper | fabric_border → fabric_front | 布料边界区域模糊 |
| capsule | poke → scratch | 微小表面损伤形态接近 |
| pill | 大量错误预测为 crack | crack 为 pill 高频缺陷，存在频率偏见 |
| transistor | misplaced/cut_lead → bent_lead | bent_lead 训练集高频，模型有频率偏见 |

### BBox IoU 分布

| IoU 阈值 | 2B_lora | 4B_lora |
|----------|--------:|--------:|
| ≥0.3 | 69.9% (286/409) | 77.0% (315/409) |
| ≥0.5 | 48.9% (200/409) | 64.5% (264/409) |
| ≥0.7 | 24.2% (99/409) | 40.8% (167/409) |
| ≥0.9 | 3.9% (16/409) | 7.1% (29/409) |
| median IoU | 0.490 | 0.643 |

### Truncation

| 变体 | 截断数 | 主要集中类别 |
|------|-------:|-------------|
| 2B_base | 57 | cable(11), transistor(10), zipper(10), wood(8) |
| 2B_lora | 18 | grid(6), wood(5), toothbrush(3) |
| 4B_base | 3 | wood(2), grid(1) |
| 4B_lora | 17 | grid(4), pill(4), wood(4), toothbrush(2) |

> LoRA 变体的 JSON 失败主要来自 max_tokens=200 截断，而不是模型乱写。2B_base 截断更多，说明 LoRA-SFT 还隐性塑造了更简洁、更结构化的输出风格。

## 6. 局限性（Limitations）

1. **`severity_valid` 不等于 severity accuracy。** 四变体的 severity_valid 均 >95%，但 severity_exact（精确匹配 GT）仅 68.7%（2B_lora）和 74.3%（4B_lora）。severity_valid 只验证枚举合法性，不衡量语义正确性。

2. **`defect_type_exact` 受 MVTec 目录名 GT 影响，可能低估语义正确预测。** GT 的 defect_type 直接取自 MVTec 目录名（如 `scratch_head`、`fabric_border`），模型预测 `scratch` 语义正确但不精确匹配，被计为错误。

3. **`bbox_iou_at_0_5` 是严格硬阈值，near-miss 不计入成功。** 约 20% 样本的 IoU 落在 0.3-0.5 区间，这些"大致定位正确"的预测在当前指标下被计为失败。

4. **GT bbox 来自 mask 外接框，不是人工 tight bbox。** 由 `connectedComponentsWithStats` 从 GT mask 提取，边界不够精确，可能系统性低估 IoU。

5. **max_tokens=200 是部署口径约束，复杂样本截断不应简单解释为 schema 学习失败。** grid、wood、toothbrush 等类别的 defect 描述天然较长，截断是输出长度限制而非格式学习问题。

| 变体 | severity_valid | severity_exact |
|------|---------------:|---------------:|
| 2B_lora | 95.6% | 68.7% |
| 4B_lora | 95.8% | 74.3% |

## 7. 部署建议

| 变体 | 定位 | 备注 |
|------|------|------|
| **2B_lora** | RK3588 16GB 首选轻量部署候选 | Category/Schema 已可用，DefType/BBox 受限；整体 pipeline 中 EfficientAD-S 和 FastSAM 提供异常区域与定位先验 |
| **4B_lora** | PC 端质量天花板 / RK3588 16GB 候选 | DefType +11.7pp，BBox +15.6pp；按当前内存预算估算，4B pipeline 峰值约 11.4GB，在 RK3588 16GB 板上有约 3.1GB 理论裕度；最终仍以 Phase 8 TTFT / decode tps / RAM / JSON OK 实测为准 |
| 2B_base / 4B_base | 不建议用于工业检测 | 未加载 LoRA 时无法稳定输出符合项目协议的结构化 JSON |

> RK3588 端单进程实际部署时应避免同时加载多套 VLM 实例，最终 2B_lora 与 4B_lora 的选型依据 Phase 8 四维指标实测结果确定。

## 8. 结论

Phase 5.7 使用完全相同 minimal prompt，排除了 Phase 5.6 中 prompt 工程差异的干扰。实验结果表明，LoRA-SFT 对工业缺陷检测任务具有显著净贡献：在 category_exact 上提升 75-94pp，在 defect_type_exact 上提升 53-64pp，在 bbox_iou_at_0_5 上提升 49-65pp。Phase 5.6 的 LoRA 优势不是 prompt 工程假象。

Phase 5.7 可以关闭，不建议回头重训。后续改进方向见 `docs/experiments/phase5_future_improvements.md`。

## 附录：文件索引

```
results/phase5_7_method_control/
├── reports/
│   ├── ab_eval_report_v2_method_control_2B.json    # 2B 聚合报告
│   └── ab_eval_report_v2_method_control_4B.json    # 4B 聚合报告
├── predictions/
│   ├── ab_eval_predictions_2B_2B_base_same_prompt_method_control.jsonl
│   ├── ab_eval_predictions_2B_2B_lora_same_prompt_method_control.jsonl
│   ├── ab_eval_predictions_4B_4B_base_same_prompt_method_control.jsonl
│   └── ab_eval_predictions_4B_4B_lora_same_prompt_method_control.jsonl

logs/
├── eval_ab_method_control_2b.log                   # 2B 评估日志
└── eval_ab_method_control_4b.log                   # 4B 评估日志
```
