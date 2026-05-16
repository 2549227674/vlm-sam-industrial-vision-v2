# Phase 5.8 OPRO Prompt-only Baseline Report

## 1. 实验动机（Motivation）

Phase 5.6 Deployment Benchmark 中，人工 engineered prompt（~300 tokens）使 2B_base 在 category_exact 上达到 53.1%。Phase 5.7 Method Control Benchmark 证明 LoRA-SFT 的净贡献不是 prompt 假象。但一个自然的后续问题是：**如果用自动化方法搜索更优 prompt，能否逼近甚至超越 LoRA？**

Phase 5.8 使用 OPRO（Optimization by PROmpting）方法，在 2B base 模型上自动搜索最优 prompt，量化 prompt-only 方法的贡献上界，并与人工 engineered prompt 和 LoRA-SFT 形成三阶段对照。

## 2. 实验设置（Experimental Setup）

### OPRO 搜索配置

| 配置项 | 值 |
|--------|-----|
| 模型 | Qwen3-VL-2B base，不加载 LoRA |
| OPRO 迭代 | 3 轮 |
| 每轮候选数 | 5 |
| 候选总数 | 15 |
| OPRO 内循环代理指标 | JSON parse / required-key success proxy |
| 标准完整评估集 | full eval split, 409 samples |
| max_tokens | 200 |
| decoding | greedy decoding, do_sample=False |

### OPRO 搜索结果

| 项目 | 数值 |
|------|------|
| seed prompt train score | 82.0% |
| best prompt train score | 98.4% |
| best prompt held-out eval score | 98.6% |
| best prompt 出现位置 | Iteration 1, Candidate 2 |
| 后续迭代 | 未超过 98.4% |

最优 prompt 内容：

> 请基于图像内容，精准判断缺陷类型。若发现缺陷，请以JSON格式返回，包含category、defect_type、severity、confidence、bboxes和description字段，bboxes需为[左上角x,y,右下角x,y]格式。

需要明确指出：98.6% 是 OPRO 搜索阶段的 held-out proxy score。该 proxy 只衡量 JSON 可解析性和 required keys 是否齐全，不是 schema_ok、category_exact、defect_type_exact 或 bbox_iou_at_0_5。因此不能直接和 LoRA 的完整评估指标比较。

## 3. OPRO 搜索结果（OPRO Search Result）

OPRO 在 3 轮迭代中搜索了 15 个候选 prompt。seed prompt（baseline）的 train score 为 82.0%，best prompt 在 Iteration 1 Candidate 2 达到 98.4% train score 和 98.6% held-out eval score。后续两轮迭代未超过该分数，搜索收敛。

best prompt 的特点是：中文短文本、要求 JSON 输出、列出了 required fields、指定了 bbox 格式为 `[左上角x,y,右下角x,y]`。它比 seed prompt 更简洁明确，但没有包含 MVTec 15 类英文枚举、severity 枚举约束或 normalized bbox 格式要求。

## 4. 标准 409-sample 完整评估（Full Evaluation）

使用 `scripts/eval_ab_test.py --mode opro --prompt-override-path` 对 full eval split（409 samples）进行标准评估：

| 变体 | JSON OK | Schema OK | Category | DefType | Severity Valid | BBox IoU≥0.5 | Avg Prompt Tok | Avg Output Tok |
|------|--------:|----------:|---------:|--------:|---------------:|-------------:|---------------:|---------------:|
| 2B_base_opro_prompt | 97.1% (397/409) | 0.0% (0/409) | 0.0% (0/409) | 0.0% (0/409) | 0.0% (0/409) | 0.0% (0/409) | 965.0 | 113.8 |

OPRO best prompt 在标准 409-sample eval set 上将 JSON OK 提升到 97.1%，但 schema_ok、category_exact、defect_type_exact、severity_valid 和 bbox_iou_at_0_5 全部为 0.0%。这说明 OPRO 找到的是一个 proxy-optimal but task-invalid prompt：它能让模型输出可解析 JSON，但不能让模型按项目工业检测协议输出正确字段值。

## 5. 跨 Phase 对比（Cross-phase Comparison）

| 变体 | JSON OK | Schema OK | Category | DefType | BBox IoU≥0.5 |
|------|--------:|----------:|---------:|--------:|-------------:|
| 2B_base + minimal（Phase 5.7） | 78.7% | 0.5% | 0.7% | 0.0% | 0.0% |
| 2B_base + OPRO（Phase 5.8） | 97.1% | 0.0% | 0.0% | 0.0% | 0.0% |
| 2B_base + engineered（Phase 5.6） | 96.1% | 96.1% | 53.1% | 11.2% | 1.5% |
| 2B_lora + minimal（Phase 5.7） | 95.6% | 95.6% | 94.4% | 53.1% | 48.9% |

关键 delta：

| 对比 | Category | DefType | BBox IoU≥0.5 |
|------|---------:|--------:|-------------:|
| 2B_lora minimal − 2B_base engineered | +41.3pp | +41.9pp | +47.4pp |
| 2B_lora minimal − 2B_base OPRO | +94.4pp | +53.1pp | +48.9pp |

## 6. 关键发现（Key Findings）

**OPRO 优化了错误的代理指标。** OPRO 内循环优化的是 JSON parse / required-key proxy。这个 proxy 与真实工业检测目标严重脱钩。一个输出如下内容的模型可以获得 JSON OK：

```json
{
  "category": "缺陷",
  "defect_type": "划痕",
  "severity": "中等",
  "confidence": 0.85,
  "bboxes": [100, 200, 300, 400],
  "description": "图像中存在缺陷"
}
```

但在真实项目中：category 不属于 MVTec 15 类英文枚举；severity 不属于 low / medium / high；bbox 不是项目要求的 normalized `{x, y, w, h}` dict；defect_type 不属于项目 taxonomy。因此 schema_ok / category / defect_type / bbox 全部失败。json_parse_ok 是工业 ontology 对齐任务中的误导性代理目标。

**OPRO 最优 prompt 是 proxy-optimal but task-invalid。** 它达到了 97.1% JSON OK，但真实任务指标全部为 0。它不是模型能力提升，而是代理指标失配导致的"假最优"。

**OPRO 最优 prompt 劣于人工 engineered prompt。** Phase 5.6 engineered prompt 明确列出了 MVTec 15 类 category 枚举、severity = low / medium / high、项目要求的 bbox 格式和更明确的 JSON schema 约束。因此 engineered prompt 达到 Category=53.1%、DefType=11.2%、BBox=1.5%，而 OPRO prompt 全部为 0.0%。向 prompt 中注入领域枚举知识比优化自然语言措辞更重要。OPRO 在错误 reward 下只搜索到了"更容易 parse 的中文短 prompt"，没有搜索到"更符合项目协议的 prompt"。

**Prompt engineering 的上界已由 Phase 5.6 engineered prompt 触及。** 在当前实验范围内，Phase 5.6 的人工 engineered prompt 是更强的 prompt-only baseline；OPRO 未能超越它。prompt-only 方法即使达到 engineered prompt 水平，仍与 LoRA-SFT 有约 41pp 的 category 差距和约 47pp 的 bbox 差距。

**LoRA-SFT 的必要性进一步增强。** Phase 5.8 进一步证明，prompt engineering 可以改善格式和部分 category 映射，但无法把通用 base 模型转化为稳定的工业检测协议模型。LoRA-SFT 将 schema、MVTec ontology、defect_type taxonomy 和 bbox annotation style 内化到模型权重中，因此不能被 prompt-only 方法替代。

## 7. 误差机制分析（Error Mechanism）

### 机制 1：category 中文化 / 泛化

OPRO prompt 没有给出 MVTec 15 类英文枚举，因此 2B_base 输出中文或泛化 category，例如：

```text
缺陷、表面缺陷、螺钉、电缆、药片缺陷、织物缺陷、机械零件、瓶盖、皮革、拉链
```

这些值对人类可读，但不是项目 schema 中的合法 category，因此 category_exact=0/409。

### 机制 2：severity 非枚举

项目要求 `low / medium / high`，但模型输出 `中等`、`轻微`、`无`、`轻度`、`低`、`严重`、`minor` 等非枚举值。因此 severity_valid=0/409。

### 机制 3：bbox 格式冲突

OPRO prompt 要求 `[左上角x,y,右下角x,y]`，模型输出整数像素坐标（如 `[698, 312, 838, 500]`）或嵌套列表。但项目 schema / eval 期望 normalized `{x, y, w, h}` dict。因此 bbox_iou_at_0_5=0/409 是必然结果。

## 8. 方法学局限（Methodological Limitations）

1. OPRO reward 使用 json_parse_ok / required-key proxy，与真实任务指标脱钩；
2. 搜索空间有限：3 轮 × 5 候选 = 15 prompts；
3. OPRO 主要探索中文短 prompt 邻域，没有探索显式英文枚举 prompt；
4. 本实验不能排除"更好设计的 OPRO"可能有效，例如以 schema_ok / category_exact / bbox_iou 为 reward；
5. 但更强 OPRO 需要每个候选跑完整 409 样本评估，计算成本显著更高，不适合作为当前阶段阻塞项；
6. 当前项目决策：不继续 OPRO，不回头重训，进入后续部署验证阶段。

## 9. 结论（Conclusion）

Phase 5.8 使用 OPRO 在 2B base 模型上搜索最优 prompt，量化 prompt-only 自动搜索的贡献上界。结果表明，OPRO 找到的 best prompt 是 proxy-optimal but task-invalid：它将 JSON OK 提升到 97.1%，但 schema_ok、category_exact、defect_type_exact、severity_valid 和 bbox_iou_at_0_5 全部为 0.0%。

Phase 5.6 / 5.7 / 5.8 共同构成三阶段论证闭环：

- **Phase 5.6 Deployment Benchmark**：LoRA 部署组合显著优于 base，但 prompt 与 LoRA 变量混合。
- **Phase 5.7 Method Control**：使用相同 minimal prompt 隔离 LoRA 净贡献，证明 LoRA 收益不是 prompt 假象。
- **Phase 5.8 OPRO Prompt-only Baseline**：自动 prompt 搜索只能优化 JSON parseability，无法替代 LoRA 的工业协议对齐能力。

最终总论：Phase 5.6 / 5.7 / 5.8 共同证明，LoRA-SFT 是本项目工业缺陷 VLM 对齐的必要环节，而不是可被 prompt engineering 替代的可选项。

## 附录：文件索引

```
results/phase5_8_opro_baseline/
├── reports/
│   └── ab_eval_report_v2_opro_2B.json
└── predictions/
    └── ab_eval_predictions_2B_base_opro_prompt.jsonl

logs/
└── eval_opro_best_2b.log
```

prompt_opro_best.json 由 AutoDL 生成，未纳入当前本地仓库。
