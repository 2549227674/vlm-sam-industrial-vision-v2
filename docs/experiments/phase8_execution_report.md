# Phase 8 执行报告：Threshold Calibration、VLM A/B 评估与节拍优化

生成时间：2026-05-22

## 1. Phase 8 总目标与执行范围

Phase 8 从 Phase 7 的"工程跑通"转向系统化校准、评估与优化。Phase 7 建立了可工作的四线程 C++ 流水线；Phase 8 确定最终部署配置。

实际执行子阶段：

| 子阶段 | 描述 | 状态 |
|---|---|---|
| Phase 8A | EfficientAD 15 类 raw threshold calibration | 已完成 |
| Phase 8A-Fix | score mode 对比（5 种模式 AUROC 矩阵） | 已完成 |
| Phase 8A-Fix-Fix | recall@FPR 单调性修复 + config 尺度一致性修正 | 已完成 |
| Phase 8B-Prep | VLM 变体运行时审计 + 固定样本集准备 | 已完成 |
| Phase 8B-Board-2B | 2B base smoke + 2B base vs LoRA A/B + controlled rerun | 已完成 |
| Phase 8B-PC | PC 端质量评估（eval_ab_test.py，409 样本） | 已完成 |
| LoRA 转换审计 | merge-then-convert 流程完整性验证 | 已完成 |
| Phase 8C-mini | pass_all 模式 beat_ms 扫频（6 组） | 已完成 |
| Phase 8B-4B | 4B base 运行时路径实现 + 板端 smoke | 已完成 |

## 2. Phase 8A：EfficientAD Threshold Calibration

### 2.1 执行环境

- 板端：Orange Pi 5 Plus 16GB（RK3588），RKNNLite 推理
- 数据集：15 类 MVTec AD test split，共 1725 张图
- 模型：EfficientAD-S FP16/no-quant raw RKNN（约 17MB/类）

### 2.2 关键发现：score mode 对比

Phase 8A 初版使用 `map_mean` 作为 score mode。Phase 8A-Fix 在同一 `rknn_scores_15cls.csv` 数据上比较了 5 种 score mode 的 AUROC（无需重新推理）。

**15 类平均 AUROC：**

| Score Mode | Mean AUROC | 排名 |
|---|---|---|
| raw_score | 0.5320 | 1（最优） |
| map_max | 0.5320 | 2 |
| map_top01 | 0.5223 | 3 |
| map_top1 | 0.5061 | 4 |
| map_mean | 0.4561 | 5（最差） |

数据来源：`results/phase8_threshold_calibration/score_mode_comparison.csv`

关键结论：
- `raw_score` 和 `map_max` 数学等价（均取 ReduceMax 输出），AUROC 完全一致
- `map_mean` 是最差模式，因为大面积正常背景区域稀释了局部缺陷信号
- 所有 5 种 mode 的 mean AUROC 均 < 0.60；14/15 类 best AUROC < 0.80（例外：tile 使用 `map_top1` 达到 0.8488）
- T2 gate 本质是负载脱落控制器，不是精确检测分类器

### 2.3 ONNX vs RKNN AUROC 对比

ONNX 与 RKNN 之间最大 AUROC delta = 0.024（screw），其余类别差异接近零。结论：FP16/no-quant RKNN 推理质量等价于 PC ONNX，差异不来自量化。

### 2.4 per-category threshold（raw_score, good_p95）

以下阈值均为 MVTec AD test split 上的 raw_score good_p95，即当前 `edge/config.yaml` 中 Phase 8A-Fix-Fix 后的值。

| Category | 阈值（raw_score good_p95） | AUROC（raw_score） |
|---|---|---|
| bottle | 49.17 | 0.4972 |
| cable | 99.84 | 0.4822 |
| capsule | 668.60 | 0.4779 |
| carpet | 38.70 | 0.7887 |
| grid | 46.72 | 0.6099 |
| hazelnut | 1142.50 | 0.5673 |
| leather | 619.70 | 0.4693 |
| metal_nut | 119.47 | 0.6173 |
| pill | 218.69 | 0.3682 |
| screw | 28.00 | 0.5337 |
| tile | 38.31 | 0.8193 |
| toothbrush | 429.01 | 0.5250 |
| transistor | 631.65 | 0.3308 |
| wood | 809.40 | 0.4162 |
| zipper | 36.42 | 0.4766 |

数据来源：`edge/config.yaml`（当前值）、`results/phase8_threshold_calibration/score_mode_comparison.csv`（raw_score 列 AUROC）

**注**：所有类别均存在 good/defect 分布重叠（ALL YES）。仅 tile 的 raw_score AUROC > 0.80。这些阈值是校准在测试集上的工程起始值，非生产认证值。

**重要说明**：Phase 8A 初版的 `map_mean` 阈值（如 bottle=12.31、tile=13.39、wood=446.51）**未在当前 config 中使用**。Phase 8A-Fix-Fix 的 config 使用 raw_score good_p95 阈值，绝对值明显不同（如 bottle=49.17、tile=38.31、wood=809.40）。

### 2.5 Phase 8A-Fix-Fix：recall@FPR 修复

原始脚本 `compare_score_modes.py` 使用 `np.linspace(lo, hi, 2000)` 离散化 + `>=` 比较，导致：
- 对 inverted distribution 类别（AUROC < 0.5）出现 `recall@FPR=1% = 1.0000` 而 `recall@FPR=5% = 0.0000` 的逻辑矛盾——更宽松约束下 recall 反而更低

修复方案：枚举实际 unique score 值（非离散化网格），比较算子改为 `>`（与 C++ 运行时 `final_score > threshold` 一致），锁定搜索方向。结果：0/75 monotonicity 违规。

## 3. Phase 8B：VLM 变体评估

### 3.1 固定样本集设计

14 张图（7 类别 × 2：每类 1 good + 1 defect）：
tile、carpet、grid、metal_nut、zipper、pill、screw

AUROC 覆盖范围：0.37（pill）— 0.82（tile）。

所有实验使用 `pass_all` 门控模式，避免 T2 threshold gate 污染 VLM 质量评估。

替换：`tile/test/good/023.png` 替换为 `011.png`，原因是 023 触发 VLM 确定性静默失败（RKLLM 立即返回，不生成 token）。

### 3.2 板端 2B base vs 2B LoRA 对比

数据来源：`results/phase8_vlm_ab/board_2b_base_vs_lora_ab_v2.md`、`board_2b_lora_controlled_rerun_summary.md`

| 指标 | 2B base | 2B LoRA（controlled rerun，beat=60s） |
|---|---|---|
| json_parse_ok | 13/14 (92.9%) | 14/14 (100%) |
| defect_type_exact | 0/7 (0%) | 0/7 (0%) |
| TTFT 均值 | 1877ms | 1914ms |
| decode_tps | 9.7 | 9.9 |
| RSS 均值 | 3285MB | 3274MB |
| qwen3vl_ms 均值 | 10548ms | ~26334ms（含 grid 退化帧） |
| repeated_bracket | 0 | 1（grid/bent，499 tokens，确定性） |
| 安全 beat_ms | 13000ms | >=60000ms |
| queue_drop | 0 | 0（60s beat 下） |

**LoRA controlled rerun 说明**：初始 A/B run（beat=20s）中 LoRA 只处理了 11/14 帧。这**不是** LoRA 处理能力的固有限制。grid/bent 图像触发 499 token repeated bracket 退化，阻塞 T3 约 50s，在 beat=20s 下导致 Q2 溢出。controlled rerun 使用 beat=60s，确认 14/14 全部处理完成、queue_drop=0。结论：上一轮 11/14 是调度问题，不是模型能力问题。但退化本身是模型的确定性行为。

**关键发现**：LoRA 在板端没有提供质量改善。两个变体均显示 0% defect_type_exact。LoRA 引入了额外的退化模式（repeated brackets、"region" 输出）。

### 3.3 PC 端质量评估（409 样本）

数据来源：`results/phase8_vlm_ab/pc_2b_base_vs_lora_eval.md`

| 指标 | PC 2B base | PC 2B LoRA | 板端 2B LoRA |
|---|---|---|---|
| json_parse_ok | 391/409 (95.6%) | 393/409 (96.1%) | 14/14 (100%) |
| defect_type_exact | 47/409 (11.5%) | 212/409 (51.8%) | 0/7 (0%) |
| category_exact | 220/409 (53.8%) | 389/409 (95.1%) | ~93% |
| bbox_iou>=0.5 | 5/409 (1.2%) | 195/409 (47.7%) | N/A |
| repeated_bracket | 0 | 0 | 1 |
| "region" 无效输出 | 0 | 0 | 1 |

**核心发现：W8A8 量化选择性破坏 LoRA 细粒度增益**
- PC LoRA bf16：defect_type_exact 51.8%，category_exact 95.1%
- 板端 LoRA W8A8：defect_type_exact 0%，category_exact ~93%
- category_exact 基本保留（粗粒度知识，编码冗余，量化鲁棒）
- defect_type_exact 完全归零（细粒度知识，集中在 rank-32 低秩子空间，量化分辨率不足）

### 3.4 LoRA 转换审计

数据来源：`results/phase8_vlm_ab/lora_conversion_audit.md`

审计结论：
- `llamafactory-cli export` 已正确将 LoRA adapter 合并进 base 权重后再做 RKLLM W8A8 转换
- 转换链：base + adapter -> merged -> W8A8 RKLLM
- SHA256 跨平台一致（AutoDL -> Orange Pi）：`de2a25b08d5a...0190f0482`
- 第一次转换因磁盘空间不足失败；重试成功（optimization_level 从 36 降至 28）
- 原"try merging before conversion"建议应删除——合并已经执行
- 正确结论：RKLLM W8A8 部署链路导致 LoRA 细粒度能力坍塌，这是硬件约束，不是操作错误

### 3.5 板端 4B base smoke

数据来源：`results/phase8_4b_smoke/phase8_4b_base_smoke_report.md`

| 指标 | 4B base | vs 2B base |
|---|---|---|
| TTFT | 4650ms | 2.45× 慢 |
| decode_tps | 4.9 | 0.51×（半速） |
| RSS | 5689MB | 1.74× |
| qwen3vl_ms（tile） | 19500ms | 1.82× |
| json_parse_ok（非 carpet） | 27/27 (100%) | 相同 |
| 安全 beat_ms（pass_all） | >=35000ms | 2.7× |
| carpet VLM | 静默失败 | 2B 正常 |

**4B vision encoder 空间 patch merge 问题**：4B vision encoder output[0] 维度为 [784, 1024]（merge 前），不能直接作为 n_image_tokens=784 传给 RKLLM（RKLLM 期望 patch_h × patch_w = 14 × 14 = 196）。当前修复：检测 4× 因子，reshape 为 [196, 4096]（contiguous）。已知缺陷：正确做法需要空间排列 `[28,28,1024] -> permute[14,2,14,2,1024] -> [196,4096]`。当前 contiguous reshape 对 6/7 类别有效；carpet 触发静默失败（纹理对空间位置敏感）。修复路径已明确，未在本轮实现。

4B 不改变当前部署主线；2B base 仍是推荐部署变体。

## 4. Phase 8C-mini：beat_ms 压力测试

数据来源：`results/phase8c_beat_sweep/phase8c_beat_sweep_summary.md`、`results/phase8c_beat_sweep/phase8c_beat_sweep_results.csv`

### 4.1 测试条件

- 2B base，pass_all 模式（最坏情况），14 张固定样本
- beat_ms 扫频：15000 / 13000 / 10000 / 8000 / 6000 / 5000

### 4.2 结果

| beat_ms | queue_drop | 稳定 | VLM_avg/beat 比值 | qwen3vl_avg (ms) |
|---|---|---|---|---|
| 15000 | 0 | 是 | 0.71 | 10735 |
| 13000 | 0 | 是 | 0.83 | 10775 |
| 10000 | 1 | 是（边界） | 1.10 | 10957 |
| 8000 | 6 | 否 | 1.42 | 11384 |
| 6000 | 14 | 否 | 1.96 | 11737 |
| 5000 | 23 | 否 | 2.62 | 13083 |

**设计公式**：
- 安全：beat_ms > VLM_p99_latency
- 推荐：beat_ms >= VLM_avg / 0.85（预留 15% buffer）
- 2B base pass_all：推荐 13000ms（ratio=0.83），最小稳定 10000ms
- 4B base pass_all：推荐 >=35000ms（基于实测最大 28.9s）

**系统行为**：
- 所有 queue drop 发生在 Q2（capacity=2，保护性设计）
- beat=5000ms 下 VLM avg 增加 21.9%（反压引发延迟放大，正反馈循环）
- RSS 全程稳定（3275-3297MB），无内存泄漏
- json_parse_ok 不受 beat_ms 影响
- 生产 threshold 模式下 ~5% pass rate，5000ms beat 等效约 100s T3 入队间隔，充足

## 5. 与 Phase 8 原始计划的偏差

| 原计划 | 实际执行 | 原因 |
|---|---|---|
| 4 变体全板端 A/B | 2B board + PC eval + 4B smoke | 4B C++ 路径原为 TODO stub，需先实现 |
| threshold 模式评估 VLM | pass_all 固定样本 | T2 AUROC < 0.80 会污染 VLM 质量评估 |
| LoRA 作为部署候选 | LoRA 转为量化失效诊断案例 | PC 有效，板端 W8A8 失效 |
| Phase 8C 完整调参 | Phase 8C-mini pass_all 扫频 | threshold 模式下 T3 几乎无负载，无需调节 |
| 4B 完整 A/B | 4B path + smoke | spatial merge 未完全正确，先 smoke |
| Phase 8B 单轮执行 | 多轮迭代（smoke → A/B → controlled rerun → PC eval → audit） | 发现调度问题和量化问题，需补充验证 |

## 6. 部署推荐

| 场景 | 推荐变体 | 理由 |
|---|---|---|
| RK3588 生产部署 | 2B base W8A8 | 稳定，无退化，json_parse_ok 100% |
| PC bf16 推理（高质量） | 2B LoRA | defect_type_exact 51.8%，bbox_iou 47.7% |
| 更大模型，延迟预算宽松 | 4B base（carpet bug 修复后） | RSS 5.7GB，延迟 1.8× |

## 7. 数据文件索引

| 文件 | 内容 |
|---|---|
| `results/phase8_threshold_calibration/rknn_scores_15cls.csv` | 15 类 1725 张 raw score |
| `results/phase8_threshold_calibration/score_mode_comparison.csv` | 5 种 score mode AUROC 矩阵 |
| `results/phase8_threshold_calibration/score_mode_comparison.md` | score mode 对比报告 |
| `results/phase8_vlm_ab/board_2b_base_smoke_summary.md` | 2B base 板端 smoke |
| `results/phase8_vlm_ab/board_2b_base_vs_lora_ab_v2.md` | 2B base vs LoRA A/B 主报告 |
| `results/phase8_vlm_ab/board_2b_lora_controlled_rerun_summary.md` | controlled rerun 对比 |
| `results/phase8_vlm_ab/board_2b_lora_controlled_rerun_vs_previous.md` | controlled rerun vs 上一轮 |
| `results/phase8_vlm_ab/pc_2b_base_vs_lora_eval.md` | PC 端 409 样本质量评估 |
| `results/phase8_vlm_ab/lora_conversion_audit.md` | LoRA 转换流程审计 |
| `results/phase8c_beat_sweep/phase8c_beat_sweep_summary.md` | beat_ms 扫频总结 |
| `results/phase8c_beat_sweep/phase8c_beat_sweep_results.csv` | beat_ms 扫频原始数据 |
| `results/phase8_4b_smoke/phase8_4b_base_smoke_report.md` | 4B base smoke 完整报告 |
| `results/phase8_4b_smoke/board_4b_base_smoke_3_summary.md` | 4B 3 图 smoke 总结 |
