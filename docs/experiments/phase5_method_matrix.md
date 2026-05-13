# Phase 5 方法学矩阵

本文档定义 Phase 5 的双轨评估设计，明确哪些方法纳入主线、哪些作为轻量对照、哪些排除。

## 1. 双轨评估设计

Phase 5 分成两条独立的评估线路，目标不同，产出不同：

### 1.1 Deployment Benchmark（部署基准）

**目标**：回答「最终上板 ship 哪个组合？」

| 变体 | 模型 | 模式 | Prompt 策略 |
|---|---|---|---|
| `2B_base` | Qwen3-VL-2B | 基座 W8A8 | 工程化 Prompt (~300 tokens) |
| `2B_lora` | Qwen3-VL-2B | LoRA W8A8 | 极简 Prompt (~50 tokens) |
| `4B_base` | Qwen3-VL-4B | 基座 W8A8 | 工程化 Prompt (~300 tokens) |
| `4B_lora` | Qwen3-VL-4B | LoRA W8A8 | 极简 Prompt (~50 tokens) |

**评估维度**（四维）：
- JSON 解析成功率（%）——PC 阶段核心指标
- TTFT（首 token 延迟，ms）——RK3588 阶段核心指标
- decode tokens/s——RK3588 阶段核心指标
- 运行时 RAM 占用（GB）——RK3588 阶段核心指标

**评估脚本**：`scripts/eval_ab_test.py --mode deployment`
**产出文件**：`results/ab_eval_report_v2_deployment.json`

### 1.2 Method Control Benchmark（方法控制基准）

**目标**：回答「LoRA 相比 base/prompt-only 的真实收益是多少？」

消除 prompt 差异的干扰，base 与 LoRA 使用完全相同的极简 prompt：

| 变体 | 模型 | 模式 | Prompt 策略 |
|---|---|---|---|
| `2B_base_same_prompt` | Qwen3-VL-2B | 基座 | 极简 Prompt (~50 tokens) |
| `2B_lora_same_prompt` | Qwen3-VL-2B | LoRA | 极简 Prompt (~50 tokens) |
| `4B_base_same_prompt` | Qwen3-VL-4B | 基座 | 极简 Prompt (~50 tokens)（可选） |
| `4B_lora_same_prompt` | Qwen3-VL-4B | LoRA | 极简 Prompt (~50 tokens)（可选） |

**评估指标**（扩展）：
- json_parse_ok / schema_ok / category_exact / defect_type_exact
- severity_valid / bbox_iou_at_0_5
- prompt_tokens / output_tokens

**评估脚本**：`scripts/eval_ab_test.py --mode method_control`
**产出文件**：`results/ab_eval_report_v2_method_control.json`

> **前提条件**：method_control 评估依赖 eval split 的 JSON 标注文件（`datasets/lora_split/*/eval/*.json`），
> 这些文件由 `scripts/mvtec_mask_to_json.py` 生成。运行评估前务必确认 eval JSON 存在。

## 2. 纳入主线的方法

以下方法是项目的正式组成部分，训练产出直接用于 RK3588 部署：

| 方法 | 模型 | 产出 | 部署链路 |
|---|---|---|---|
| LoRA-SFT (2B) | Qwen3-VL-2B | `models/qwen3vl_lora_adapter_15cls/` | LLaMA-Factory export → RKLLM W8A8 |
| LoRA-SFT (4B) | Qwen3-VL-4B | `models/qwen3vl_lora_4b_adapter/` | LLaMA-Factory export → RKLLM W8A8 |

**超参固定**：
- LoRA rank: 16, alpha: 16, dropout: 0.05
- target: q_proj, v_proj
- freeze_vision_tower: true
- freeze_multi_modal_projector: true
- 5 epochs, cosine scheduler, warmup 0.1

## 3. 纳入轻量对照的方法

以下方法不训练参数、不进入 RK3588 部署链路，仅作为 PC 阶段的方法学对照：

### 3.1 OPRO / Prompt-only Baseline

**原理**：用 LLM 自身搜索更优的 prompt，不修改模型参数。

**实现**：`scripts/optimize_prompt_opro.py`
- 用少量 train 子集（~30 samples/category）搜索 prompt
- eval 集严格隔离评估
- 输出 best prompt 到 `results/prompt_opro_best.json`

**价值**：
- 量化 prompt engineering 的单独贡献
- 与 LoRA 形成对照：LoRA 的收益中，有多少来自「短 prompt 更易遵循」vs 「参数适应」

### 3.2 2B Freeze Pilot（可选）

**原理**：只训练 LoRA adapter，冻结全部其他参数（包括 vision tower 和 projector）。与主线 LoRA-SFT 相同，此为默认行为。

### 3.3 2B Full SFT Pilot（可选，上界参考）

**原理**：全参数 SFT，不使用 LoRA。显存需求大幅增加（~16GB+），仅在 A100 级别 GPU 上可行。

**价值**：
- 提供 LoRA 的理论上界：如果 full SFT 只比 LoRA 好 1-2%，说明 LoRA 已足够
- 不作为主线，不产出部署权重

## 4. 排除的方法

以下方法不纳入本项目的任何评估或部署：

### 4.1 Soft Prompt / Prompt Tuning

**排除原因**：不适合 RKLLM 部署链路。RKLLM runtime 不支持 soft prompt 输入，只接受纯文本 token。soft prompt 需要额外的 embedding 注入机制，在当前部署框架下无法实现。

### 4.2 AutoPrompt

**排除原因**：生成的 prompt 可读性差（由离散 token 拼接而成），不适合需要人工审查的工业场景。且 RK3588 端需要将 prompt 硬编码到 C++ 代码中，不可读的 prompt 增加维护成本。

### 4.3 GCG（Greedy Coordinate Gradient）

**排除原因**：GCG 是对抗性攻击方法，生成的 adversarial suffix 可触发模型的不安全行为。本项目面向工业质检，安全性和可解释性是基本要求，不适用攻击类方法。

### 4.4 Adapter Fusion

**排除原因**：本项目是单任务场景（MVTec AD 缺陷检测），Adapter Fusion 在多任务/多领域融合时才有优势。单任务下 adapter fusion 不会带来额外收益，反而增加推理复杂度。

## 5. 决策流程图

```
Phase 5 评估
├── Deployment Benchmark（4 变体，不同 prompt）
│   └── → 选出 ship 到 RK3588 的最优组合
│
├── Method Control Benchmark（同 prompt，隔离 LoRA 效应）
│   └── → 量化 LoRA 的真实收益
│
└── OPRO Prompt-only Baseline
    └── → 量化 prompt engineering 的单独贡献
```

**最终决策依据**：
1. Deployment Benchmark 的 JSON 成功率 + RK3588 四维指标 → 选定 ship 变体
2. Method Control 的 delta → 确认 LoRA 是否值得额外的训练和部署成本
3. OPRO baseline → 确认 prompt engineering 的天花板

## 6. 配套脚本清单

| 脚本 | 用途 | 运行环境 |
|---|---|---|
| `scripts/split_lora_data.py` | 数据划分（70/30 train/eval） | PC，一次性 |
| `scripts/mvtec_mask_to_json.py` | GT mask → JSON 标注（train + eval 双 split） | PC，一次性 |
| `scripts/format_llama_factory_data.py` | JSON → ShareGPT 格式（含 dry-run 校验） | PC，一次性 |
| `scripts/eval_ab_test.py` | Deployment + Method Control 评估 | PC（GPU） |
| `scripts/optimize_prompt_opro.py` | OPRO prompt-only baseline | PC（GPU） |
| `qwen3vl_lora.yaml` | 2B LoRA 训练配置 | AutoDL / PC |
| `qwen3vl_lora_4b.yaml` | 4B LoRA 训练配置 | AutoDL |

## 7. 输出文件清单

```
results/
├── ab_eval_report_v2_deployment.json      # Deployment benchmark 结果
├── ab_eval_report_v2_method_control.json  # Method control benchmark 结果
└── prompt_opro_best.json                  # OPRO 最优 prompt + 评估分数

models/
├── qwen3vl_lora_adapter_15cls/            # 2B LoRA v2 adapter
└── qwen3vl_lora_4b_adapter/               # 4B LoRA adapter
```
