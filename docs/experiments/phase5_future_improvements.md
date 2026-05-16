# Phase 5 后期改进方向

本文档整理 Phase 5.6 Deployment Benchmark 和 Phase 5.7 Method Control Benchmark 中暴露的已知局限，并按可操作性分层提出改进方向。

当前决策：上述局限均不作为 Phase 5.7 前置阻塞项，不回头重训，不修改 GT，不重新生成数据集。本文档作为后期改进参考。

## 1. 指标体系局限（已知，当前不改）

| 局限 | 影响 | 当前处理 |
|------|------|----------|
| `severity_valid` 只验证枚举合法性，不衡量语义正确性 | severity 精度被高估 | 接受，不阻塞 |
| `defect_type_exact` 受 MVTec 目录名 GT 影响 | 语义正确但名称不精确的预测被计为错误 | 接受，defect_group_exact 作为辅助参考 |
| `bbox_iou_at_0_5` 是硬阈值 | near-miss（IoU 0.3-0.5）不计入成功 | 接受，报告中补充 IoU 分布表 |
| GT bbox 来自 mask 外接框，非人工 tight bbox | 系统性低估 IoU | 接受，不修改 GT |
| max_tokens=200 截断影响复杂样本 | grid/wood/toothbrush 等长描述类别受压 | 接受，截断敏感性补测已做辅助说明 |

这些局限在 Phase 5.6/5.7 报告中均有记录，不影响 LoRA vs base 的对比结论，当前不修改。

## 2. 模型能力瓶颈（可改，超出当前项目范围）

### 2a. DefType 细粒度混淆

Phase 5.7 中 LoRA 变体的 defect_type_exact 为 53.1%（2B）和 64.8%（4B）。典型混淆模式：

- **cable**: cut_inner ↔ cut_outer_insulation（内外绝缘层视觉高度相似）
- **screw**: manipulated_front → thread_top（螺纹视角依赖性）
- **zipper**: fabric_border → fabric_front（布料边界区域模糊）
- **capsule**: poke → scratch（微小表面损伤形态接近）
- **pill**: 大量错误预测为 crack（频率偏见）
- **transistor**: misplaced/cut_lead → bent_lead（频率偏见）

这些混淆的根源是 MVTec AD 部分类别的子类型视觉差异极小，仅凭单帧 RGB 图像难以区分。改进方向包括尝试更高 LoRA rank（视当前训练配置而定）、增加训练数据多样性、或引入多视角/多模态输入，但均超出当前项目范围。

### 2b. BBox 精度与 near-miss

Phase 5.7 中 BBox IoU≥0.5 为 48.9%（2B_lora）和 64.5%（4B_lora），但 IoU≥0.3 达到 69.9% 和 77.0%。大量样本落在 0.3-0.5 区间，属于"大致定位正确但不够精确"。

VLM 的 bbox 输出本质上是语言生成的坐标 token，精度受限于：
- 输出坐标精度（归一化到 0-1000 的整数 token）
- 图像分辨率与目标尺寸比
- 训练数据中 bbox 标注的精确度

改进方向：尝试更高 LoRA rank（视当前训练配置而定）可能提升 bbox 回归精度，但收益递减。更根本的改进需要引入专用检测头或 SAM 后处理。

### 2c. transistor / wood bbox 天花板

transistor 和 wood 的 BBox IoU≥0.5 在 2B_lora 和 4B_lora 上均较低（transistor: 3/12, wood: 14/20）。这两个类别的缺陷区域特征：
- transistor: 引脚弯曲/偏移的视觉边界模糊
- wood: 木纹缺陷与正常纹理的边界不清晰

GT bbox 本身也不够精确（来自 mask 外接框），进一步压低了 IoU。这不是 LoRA 能解决的问题。

## 3. 工程改进方向（当前可操作）

### 3a. C++ 侧枚举白名单后处理（部署必做）

VLM 输出的 category / severity 可能包含非项目枚举值（尤其是 base 模型，LoRA 后大幅改善但仍需兜底）。C++ 部署端应在 JSON 解析后做枚举白名单校验：

```cpp
static const std::unordered_set<std::string> VALID_CATEGORIES = {
    "bottle","cable","capsule","carpet","grid","hazelnut","leather",
    "metal_nut","pill","screw","tile","toothbrush","transistor","wood","zipper"
};

static const std::unordered_set<std::string> VALID_SEVERITIES = {
    "low","medium","high"
};
```

不在白名单内的值应 fallback 到默认值并计入 metrics，不丢弃整条检测结果。

### 3b. severity_exact 补充评估脚本

当前 Phase 5.6/5.7 报告中的 severity 数据来自评估脚本的直接输出。建议补充一个独立的 severity_exact 评估脚本，对已有 JSONL prediction 文件做后处理统计，不需要重跑模型。

### 3c. max_tokens=300 截断补测（可选）

Phase 5.6 已做 max_tokens=300 截断敏感性补测（仅截断子集）。如需更完整的对比，可对 Phase 5.7 全量 eval 集用 max_tokens=300 重跑，但优先级低。

### 3d. defect_group_exact 统一口径

Phase 5.6 报告中使用了 defect_group_exact 作为辅助分析指标，Phase 5.7 未单独报告。建议跨 Phase 统一 defect_group alias 映射表，确保可比性。

## 4. 与整体 Pipeline 架构的关系

本项目的三段式流水线（EfficientAD-S → FastSAM → Qwen3-VL）中，VLM 是最后一环，负责结构化描述输出。前两段的贡献：

- **EfficientAD-S**：提供异常检测二分类和 anomaly map，降低 VLM 需要"判断是否有缺陷"的负担
- **FastSAM**：提供 mask 和 crop bbox，降低 VLM 独立 bbox 定位的压力

但 defect_type 的细粒度语义识别仍主要依赖 VLM-LoRA。EfficientAD-S 和 FastSAM 不提供 defect_type 信息，无法补偿 VLM 在子类型混淆上的不足。

## 5. 下一阶段优先级

| 优先级 | 任务 | 依赖 |
|--------|------|------|
| P0 | C++ 侧枚举白名单 | 部署前必须完成 |
| P0 | Phase 8 RK3588 16GB 四维指标实测 | 板子与 RKLLM 部署环境 |
| P1 | severity_exact 补充评估 | 不需要重跑模型 |
| P1 | Phase 5.8 OPRO prompt-only baseline | AutoDL 资源 |
| P2 | max_tokens=300 截断补测 | AutoDL 资源 |
| P2 | defect_group_exact 跨 Phase 统一 | 不需要重跑模型 |
| P3 | DefType 精度提升 | 新训练周期，超出当前范围 |
