# 工程排错与发现记录

本文档记录 vlm-sam-industrial-vision-v2 项目中遇到的关键工程问题、排查过程与解决方案。按组件分类，时间顺序排列。

---

## 1. EfficientAD 部署

### F-EAD-01：post-processor 输出与 RKNN 不兼容

**阶段**：Phase 7 Prompt 2B
**现象**：直接导出含 Anomalib post-processor 的 ONNX 模型后，RKNN 转换失败，报错 `Greater` 算子不支持 INT8/FLOAT 混合类型。
**根因**：post-processor 包含 clip → normalize → sigmoid 操作，其中 `Greater` 节点需要 FLOAT 和 INT8 混合比较，Rockchip RKNN toolkit 不支持。
**解决方案**：导出 raw ONNX（去除 post-processor），使用 `/model/ReduceMax_output_0` 作为 `raw_score`，`/model/Add_output_0` 作为 `raw_anomaly_map`。新增 `scripts/export_efficientad_raw_onnx.py` 实现截断导出。
**工程影响**：T2 gate 只能使用 raw output，分数尺度与原 post-processor 输出 [0,1] 范围完全不同。per-category 阈值需从头校准。

### F-EAD-02：INT8 RKNN 分布失真

**阶段**：Phase 7 Prompt 2B
**现象**：EfficientAD INT8 量化 RKNN 推理结果的 anomaly map 分布与 ONNX 严重偏离，good 和 defect 样本分数几乎无区别。
**根因**：INT8 量化对 EfficientAD 的 raw anomaly map 值域（跨度大、动态范围宽）捕获不足，量化后分布失真。
**解决方案**：改用 FP16/no-quant RKNN（`rknn_init` 时不做量化）。验证：ONNX vs RKNN max AUROC delta = 0.024（screw），其余类别差异可忽略。
**工程影响**：FP16 RKNN 每类约 17MB（INT8 约 5MB），但推理速度可接受。15 类全部转换为 FP16/no-quant。

### F-EAD-03：score mode 选择影响 AUROC

**阶段**：Phase 8A-Fix
**现象**：Phase 8A 使用 `map_mean` 得到的全 15 类 AUROC 均 < 0.50，近似随机猜测。
**根因**：`map_mean` 将 anomaly map 所有像素取平均，大面积正常背景区域拉低均值，局部缺陷信号被稀释。对局部缺陷类别（grid、wood、zipper）影响尤其严重。
**解决方案**：对 5 种 score mode 计算 AUROC 矩阵（复用已有 CSV，无需重新推理），发现 `raw_score`（ReduceMax）mean AUROC = 0.5320 vs `map_mean` 0.4561（delta = +0.0759）。切换 `efficientad_score_mode: raw_score`，更新所有 15 类阈值为 raw_score good_p95。
**工程影响**：grid 类别改善最大（+0.3241 AUROC），证实局部缺陷检测需要基于最大像素值的评分，而非均值。

### F-EAD-04：recall@FPR 计算 bug

**阶段**：Phase 8A-Fix-Fix
**现象**：部分类别出现 `recall@FPR=1% = 1.0000` 而 `recall@FPR=5% = 0.0000` 的逻辑矛盾——更宽松约束下 recall 反而更低。
**根因**：`compare_score_modes.py` 使用 `np.linspace(lo, hi, 2000)` 离散化阈值，精度不足；同时使用 `>=` 而非 `>`，与 C++ 运行时 `final_score > threshold`（严格大于）不一致。对 AUROC < 0.5 的 inverted distribution 类别，脚本尝试翻转方向搜索，产生方向相反的"高 recall"结果。
**解决方案**：改为枚举实际 unique score 值（非离散化网格），比较算子改为 `>`，锁定搜索方向为 `score > threshold`（与运行时一致），添加单调性断言验证。结果：0/75 recall@FPR 违规。
**工程影响**：确保诊断指标正确反映运行时决策边界，防止报告中出现误导性 recall@FPR 值。

---

## 2. FastSAM 部署

### F-FSM-01：INT8 量化精度回退

**阶段**：Phase 7 Prompt 2C
**现象**：FastSAM INT8 RKNN 在部分类别（capsule）产生严重偏移的检测框。检测置信度坍塌至近零（raw candidates=0，100% fallback）。
**根因**：INT8 per-tensor quantization（scale=2.82, zp=-119）将 YOLOv8 置信度压缩到近零范围。全部 8400 个 anchor 的 conf < 0.25。FP16 top-1 conf = 0.8794，INT8 top-1 conf ≈ 0.003。
**解决方案**：改用 FP16/no-quant RKNN（`do_quantization=False`），输出 `fastsam_s_noquant.rknn`（26MB）。FP16 模式 fallback 率：0%（0/31 帧）。
**工程影响**：FastSAM FP16 推理约 170ms（预处理 ~95ms + 推理 ~140ms + 后处理 ~7ms），在流水线延迟预算内可接受。

### F-FSM-02：FastSAM 校准集策略

**阶段**：Phase 6（v2 转换）
**现象**：Phase 5 的 3 类校准集转换的 FastSAM INT8 RKNN，在扩展到 15 类后部分类别量化偏差更大。
**根因**：INT8 校准集只有 3 类，激活分布代表性不足。
**解决方案**：使用 15 类混合校准集（约 300 张，`random.seed(42)` 混洗），重新转换 FastSAM RKNN（最终仍用 FP16/no-quant）。
**工程影响**：即使校准集改进后，INT8 精度仍不可接受。FP16 是 FastSAM 在 RK3588 上唯一可行的量化级别。

---

## 3. Qwen3-VL / RKLLM 部署

### F-VLM-01：RKLLM runtime 版本不匹配

**阶段**：Phase 7 Prompt 2D
**现象**：`rkllm_init` 失败，报错 `The rkllm-runtime version is lower than the rkllm-toolkit version. Please update to 1.2.3`。
**根因**：板上 `/usr/lib/librkllmrt.so` 为 v1.2.1，模型由 rkllm-toolkit 1.2.3 导出。
**解决方案**：替换系统库为 `/home/orangepi/rkllm_run/librkllmrt.so`（v1.2.3）。

### F-VLM-02：n_image_tokens 计算错误

**阶段**：Phase 7 Prompt 2D
**现象**：`E rkllm: patch_h[14] * patch_w[14] != n_image_token[784]!`
**根因**：代码设置 `n_image_tokens = 196 * 4 = 784`（误乘了 n_output）。RKLLM 期望 `n_image_tokens = patch_h * patch_w = 14 * 14 = 196`。
**解决方案**：改为直接使用 `vision_image_token_`（196），不做乘法。

### F-VLM-03：max_new_tokens 导致 JSON 截断

**阶段**：Phase 7 Prompt 2D
**现象**：VLM 输出在 bboxes 数组中间截断，`rfind('}')` 无法找到配对括号。
**根因**：`vlm_max_new_tokens: 200`，VLM 实际输出达 ~196 tokens 时截断。
**解决方案**：
1. 增加 `vlm_max_new_tokens` 至 500
2. 优化 prompt 为 compact JSON（`[[x,y,w,h]]` 格式），将输出从 ~196 降至 ~89 tokens
3. JSON 提取改为 `rfind('}')` 容忍不完整输出

### F-VLM-04：2B LoRA W8A8 量化破坏细粒度分类能力

**阶段**：Phase 8B-PC + LoRA 转换审计
**现象**：PC bf16 推理 defect_type_exact = 51.8%，板端 W8A8 RKLLM 推理 = 0%。category_exact 基本保留（95.1% → 93%），defect_type_exact 完全归零。
**根因**：LoRA rank=32 的 delta 权重幅值相对 base 权重小约 1-2 个数量级。W8A8 量化 step size = max(|W|)/127，对 base 权重合适，对 LoRA delta 精度不足，delta 被量化为零，fine-grained 知识丢失。
**验证**：LoRA 已正确 merge-then-convert（bash_history + LoRA key 检验 + SHA256 跨平台一致），不是转换错误。
**解决方案**：RK3588 LLM 路径仅支持 W8A8（W4A16 仅 RK3576）。部署选择：2B base（稳定），LoRA 保留 PC bf16 推理价值。
**工程影响**：W8A8 量化对小幅值 delta 权重的破坏是硬件层面的根本约束，非训练或转换失败。

### F-VLM-05：LoRA 在特定输入上确定性退化（重复括号）

**阶段**：Phase 8B-Board
**现象**：`grid/bent/011.png` 每次触发 2B LoRA 输出 499 tokens 的括号重复：`[[[0.00220382, 0.00220382, 0.0528917, 0.0440764], [[0.00440764, ...`
**根因**：LoRA 训练数据中 grid/bent 类别可能包含多层嵌套 bbox 格式样本，LoRA adapter 学到了"bent → 多层嵌套坐标"的映射，W8A8 推理时进入循环，直到 max_tokens 截断。
**工程影响**：阻塞 T3 约 50 秒，beat=20s 下导致 Q2 溢出，后续 3 帧被 drop。
**解决方案**：板端不部署 LoRA。如需 LoRA，beat_ms >= 60000ms，或添加输出后处理检测括号重复并截断。

### F-VLM-06：4B vision encoder spatial patch merge 排列错误

**阶段**：Phase 8B-4B
**现象**：`E rkllm: patch_h[14] * patch_w[14] != n_image_token[784]!`（4B 初始化失败）。修复为 196 后，carpet 类别触发静默 VLM 失败（vision_ms=0，无错误输出）。
**根因**：4B vision encoder output[0] 为 [784, 1024]（spatial merge 前），output[1-4] 为 [196, 2560]。n_image_tokens 应为 196，embed_dim 应为 4096（=1024×4）。当前 contiguous reshape [784,1024]→[196,4096] 逻辑上正确但空间排列错误。正确做法：`[28,28,1024] → permute[14,2,14,2,1024] → [196,4096]`。carpet 纹理对空间位置敏感，错误排列产生 RKLLM 无法处理的 embedding。
**当前状态**：6/7 类别正常，carpet 静默失败。修复路径已明确，未实现。
**对 2B 无影响**：2B 无 spatial merge，代码路径独立。

---

## 4. C++ 四线程流水线

### F-CPP-01：beat_ms 与 VLM 延迟的队列稳定性关系

**阶段**：Phase 8C
**发现**：VLM_avg_ms / beat_ms 是队列稳定性的关键指标（对应排队论的服务强度 ρ）。当 ratio > 1.0，Q2 开始积压；> 1.5 时严重不稳定。
**设计公式**：
- 安全：beat_ms > VLM_p99_latency
- 推荐：beat_ms >= VLM_avg / 0.85（预留 15% buffer）
- 2B base：推荐 13000ms，最小稳定 10000ms
- 4B base：推荐 >=35000ms（实测 screw 最大 28.9s）

### F-CPP-02：反压引发 VLM 延迟放大

**阶段**：Phase 8C
**现象**：beat=5000ms 下 VLM avg 从基线 10.7s 上升到 13.1s（+21.9%）。
**根因**：Q2 持续满载时，T2 在 push 等待中消耗 CPU/调度时间；VLM 与 EfficientAD/FastSAM 在 NPU 资源上形成竞争，导致 VLM 单帧时间增加。正反馈：VLM 慢 → 更多积压 → NPU 更拥挤 → VLM 更慢。
**工程影响**：系统在 Q2 满载时不是线性退化，而是加速退化。beat_ms 扫频中 queue drop 呈指数增长趋势。

---

## 5. 实验方法论

### F-METHOD-01：timeout / 未 drain 完导致实验数据不完整

**阶段**：Phase 8B LoRA 初始 A/B
**现象**：LoRA v2 run 只处理 11/14，误判为"LoRA 处理能力不足"。
**根因**：Claude Code 远程执行设置的 timeout 可能在 LoRA 处理完 14 张之前到期，日志被截断，后端也只有 11 条记录。
**解决方案**：补充 controlled rerun，设置明确足够长的 timeout（1800s），使用后端 poll 确认 14/14 后发送 SIGTERM。结论：11/14 是调度问题（beat=20s 不够 50s 的 grid 退化帧），不是 LoRA 本身处理能力问题。

### F-METHOD-02：calibration-on-test 的方法论声明

**阶段**：Phase 8A
**问题**：Phase 8A 用 MVTec test split 同时做阈值校准和指标评估（calibration-on-test）。
**影响**：AUROC 不受影响（纯排序指标）；recall@FPR 和 F1 有轻微乐观偏差。
**处理**：summary.md 中明确声明。MVTec 样本量有限（最少 12 张 good），50/50 分割会使分位数估算更不稳定。
**领域惯例**：anomaly detection 论文（包括 EfficientAD 原论文）均在同一 test split 上报 AUROC。

### F-METHOD-03：pass_all vs threshold 的评估边界

**阶段**：Phase 8B
**问题**：使用 threshold 模式做 VLM 质量评估时，T2 gate 会非随机地过滤帧（因 AUROC < 0.80），污染 VLM 质量对比。
**决策**：所有 VLM A/B 评估使用 pass_all 以保证样本无偏覆盖。T2 gate 行为在 Phase 8A（校准）和 Phase 7 Prompt 2F（threshold 验证）中单独评估。

---

## 6. 模型转换与量化

### F-QUANT-01：RKLLM 第一次转换因磁盘不足失败

**阶段**：Phase 6（2B LoRA 转换）
**现象**：Export 在 399/399 层转换完成后失败，`Not enough free space to write 129,679,360 bytes`。
**解决方案**：清理 AutoDL 磁盘，重试。Retry 成功但 optimization_level 从 36 降至 28，对推理结果影响可忽略。

### F-QUANT-02：transformers 版本冲突处理

**阶段**：Phase 6 RKLLM 转换
**现象**：rkllm-toolkit 1.2.3 锁定 transformers==4.55.2，但生成校准数据需要 transformers==4.57.0（支持 Qwen3-VL）。
**解决方案**：操作顺序管理：
1. 生成校准数据前临时升级：`pip install transformers==4.57.0`
2. export_rkllm.py 执行前降回：`pip install transformers==4.55.2 tokenizers==0.21.4`

### F-QUANT-03：LoRA merge-then-convert 审计

**阶段**：Phase 8B
**问题**：初始 PC 评估建议"try merging LoRA before RKLLM conversion"——但合并已经执行。
**证据**：
- `merge_2b_lora_15cls.yaml` 确认 base + adapter 路径
- `llamafactory-cli export` 已执行（bash_history line 83）
- 合并后 Python 验证："No LoRA keys — merge confirmed"
- 4B merge log 确认相同机制
- SHA256 在 AutoDL 和 Orange Pi 之间完全一致
**正确结论**：转换链（merge → W8A8 convert）是正确的。质量坍塌由 W8A8 量化破坏 LoRA delta 权重导致，非操作错误。

### F-QUANT-04：W8A8 对 LoRA delta 不友好

**阶段**：Phase 8B（跨阶段）
**根因**：LoRA rank-32 delta 权重（~51MB，占总参数 ~0.1%）的幅值比 base 权重小 1-2 个数量级。W8A8 量化分辨率（max(|W|)/127）按 base 权重分布校准，对 delta 精度不足。delta 被量化为零或近零，fine-grained 知识丢失。
**证据**：PC bf16 LoRA 达到 51.8% defect_type_exact；板端 W8A8 LoRA 为 0%。category_exact 存活（95.1% → 93%），因为粗粒度 category 知识在多个大幅值权重上编码冗余。
**启示**：任何小幅值 fine-tuning delta（不限于 LoRA）在 W8A8 下都面临类似退化。这是 INT8 权重量化对增量学习的根本精度限制。
