# Phase 7 Edge Pipeline Engineering Report

## 1. 摘要

Phase 7 在 Orange Pi 5 16GB（RK3588）上完成 C++ 四线程推理流水线从 Mock 到真实推理的全链路工程验证。覆盖 Prompt 2B ~ 2F 共 6 个子阶段，实现 EfficientAD-S → FastSAM → Qwen3-VL → Upload 完整闭环。

当前冻结点：

```text
四线程流水线工程验证通过。
默认稳定模型：EfficientAD FP16 raw + FastSAM FP16/no-quant + Qwen3-VL 2B base W8A8。
2E True E2E PASS：upload_ok=24/24, json_parse_ok=100%, RSS=3324MB。
2F threshold gate 可观测，T3 压力可按阈值调控。
```

## 2. 板端环境

```text
Board:          Orange Pi 5 16GB (RK3588)
OS:             Ubuntu 22.04 Jammy
GCC:            11.4.0
RKNN Runtime:   librknnrt.so v2.2+
RKLLM Runtime:  librkllmrt.so v1.2.3（从 v1.2.1 升级）
Backend:        WSL 192.168.137.1:8000 (FastAPI + SQLite WAL)
```

## 3. 模型资产

| 模型 | 格式 | 大小 | 用途 |
|---|---|---|---|
| EfficientAD-S (15 类) | FP16/no-quant RKNN | 各 ~2MB | T2 异常检测 |
| FastSAM-s | FP16/no-quant RKNN | 26 MB | T3 分割 |
| Qwen3-VL 2B base | W8A8 RKLLM | 2.3 GB | T3 VLM |
| Qwen3-VL 2B vision | FP16 RKNN | 812 MB | T3 Vision encoder |
| Qwen3-VL 2B LoRA | W8A8 RKLLM | 2.3 GB | T3 VLM（LoRA 变体） |
| Qwen3-VL 4B base | W8A8 RKLLM | 4.6 GB | 待验证 |
| Qwen3-VL 4B vision | FP16 RKNN | 843 MB | 待验证 |

不提交大模型文件到 Git。

## 4. Pipeline 架构

```text
T1 CaptureWorker (jthread)
  └─ Q1(cap=4, drop-oldest)
T2 EadWorker (jthread)
  ├─ EfficientAD FP16 raw RKNN
  ├─ score_mode=map_mean
  ├─ gate_mode=threshold / pass_all
  ├─ per_category_threshold
  └─ Q2(cap=2, drop-oldest)
T3 FastSamWorker (jthread)
  ├─ FastSAM FP16/no-quant RKNN
  ├─ 5-level bbox cleanup
  ├─ VLM bbox fusion (IoU>0.3)
  ├─ Qwen3-VL 2B W8A8 RKLLM
  ├─ compact JSON prompt
  ├─ JSON extraction + 3-level fallback
  └─ Q3(cap=4, drop-oldest)
T4 UploadWorker (jthread)
  ├─ libcurl multipart POST
  ├─ schema_version=v1
  ├─ trace_events (6 events)
  └─ 指数退避重试（5 次）
```

### 可观测指标（PipelineMetrics）

| 指标 | 含义 |
|---|---|
| `capture_count` | T1 取帧总数 |
| `ead_count` | T2 推理总数 |
| `ead_gate_pass` | T2 通过 gate 推入 Q2 |
| `ead_gate_drop` | T2 阈值拦截不进 Q2 |
| `vlm_count` | T3 VLM 完成总数 |
| `upload_count` | T4 上传成功 |
| `upload_failed` | T4 上传失败 |
| `dropped_count` | Q1+Q2+Q3 队列满丢帧总和 |

### trace_events 完整列表

| 事件 | 线程 | 含义 |
|---|---|---|
| efficientad_infer | T2 | EfficientAD RKNN 推理 |
| fastsam_preprocess | T3 | 图像预处理 + resize |
| fastsam_infer | T3 | FastSAM RKNN 推理 |
| fastsam_postprocess | T3 | bbox 解码 + NMS + cleanup |
| qwen3vl_generate | T3 | VLM 全链路（vision + LLM） |
| upload | T4 | HTTP multipart 上传 |

## 5. 子阶段成果

### 5.1 Prompt 2B：EfficientAD FP16 Raw

**核心发现**：Anomalib ONNX 的 post_processor 输出（`pred_score/anomaly_map`）经 Clip 归一化后 good/defect 均饱和到 ~1.0，不可用于 gate。`Greater` INT8/FLOAT 节点在 RKNN Runtime 触发类型不支持。

**解决方案**：导出 post_processor 前 raw tensor（`raw_score`, `raw_anomaly_map`），转换为 FP16/no-quant RKNN。

**验收**：bottle / metal_nut / pill / screw 4 类 FP16 raw RKNN 工程验证通过。

### 5.2 Prompt 2C/2C-Fix：FastSAM FP16/no-quant

**核心发现**：INT8 per-tensor quantization（scale=2.82）将 YOLOv8 置信度压缩到近零（top-1 ≈ 0.003），100% fallback。

**解决方案**：FP16/no-quant RKNN（`do_quantization=False`），conf 恢复到 0.7-0.88，0% fallback。

**新增**：5 级 bbox cleanup（边界裁剪 → 面积过滤 → IoU 去重 → 数量限制）。

### 5.3 Prompt 2D/2D-Fix：Qwen3-VL 2B Base

**核心发现**：RKLLM runtime 版本不匹配（v1.2.1 vs v1.2.3）；`n_image_tokens` 语义混淆（应为 196 而非 784）；200 token 输出限制导致 JSON 截断。

**解决方案**：升级 runtime；修正 n_image_tokens；compact JSON prompt 将输出从 196 降至 ~89 tokens。

**Prompt 2D-Fix 修补**：VLM bbox 归一化 + 保守融合（IoU>0.3）；severity 白名单 low/medium/high；LoRA/variant 路径选择；upload trace_event。

### 5.4 Prompt 2E：True E2E PASS

**结果**：8 图 4 类，24 帧全部成功上传。upload_ok=24/24, json_parse_ok=100%, 0 fallback, 0 dropped, Backend 24 条记录可查。

### 5.5 Prompt 2F：Threshold 模式验证

**结果**：覆盖型（低阈值）21/21 帧通过 gate；过滤型（高阈值）8/21 帧通过，T3 压力下降 65%。gate_drop 可观测，队列 dropped=0。

## 6. 关键工程修复

| 问题 | 根因 | 解决方案 |
|---|---|---|
| EfficientAD post_processor 饱和 | Clip 归一化输出 good/defect 均 ≈1.0 | 导出 raw tensor，FP16/no-quant |
| EfficientAD INT8 raw 分布失真 | INT8 量化精度不足 | 放弃 INT8，使用 FP16 |
| FastSAM INT8 conf 近零 | per-tensor scale=2.82 压缩过度 | FP16/no-quant |
| RKLLM runtime 版本不匹配 | 板上 v1.2.1 vs toolkit v1.2.3 | 替换 librkllmrt.so |
| n_image_tokens 错误 | 代码设置 196×4=784，RKLLM 期望 196 | 改为 patch_h × patch_w |
| JSON 截断 | max_new_tokens=200 不够 | 提升至 500 + compact JSON |
| VLM bbox 未归一化 | 像素坐标直接使用 | 除以 orig_w × orig_h |
| severity 语义不一致 | critical 无标准定义 | 白名单 low/medium/high |
| gate_drop 不可观测 | PipelineMetrics 无区分 | 新增 ead_gate_pass/drop |

## 7. 性能汇总

| 指标 | 值 | 来源 |
|---|---|---|
| EfficientAD 平均 | 350.8 ms | 2E 后端聚合 |
| FastSAM 平均 | 250.1 ms | 2E 后端聚合 |
| Qwen3-VL 平均 | 11,350 ms | 2E 后端聚合 |
| TTFT 平均 | 2,174 ms | 2E 后端聚合 |
| Decode tps | 9.97 | 2E 后端聚合 |
| Output tokens | 54-92 | 2E/2F 实测 |
| Prompt tokens | 478 avg | 2E 后端聚合 |
| RSS | 3,324 MB | 2E/2F 稳定无增长 |
| Upload ms | 16-47 ms | 2E/2F 实测 |

## 8. E2E 验收

| 指标 | 2E 结果 |
|---|---|
| upload_ok | 24/24 |
| upload_fail | 0 |
| json_parse_ok | 100% |
| fallback_frames | 0 |
| dropped_count | 0 |
| Categories covered | 4/4 (bottle, metal_nut, pill, screw) |
| Backend records | 24 条可查 |
| trace_events | 6/6 完整 |

## 9. Threshold 模式

| 指标 | 2F-A（覆盖型） | 2F-B（过滤型） |
|---|---|---|
| gate_pass_rate | 100% (21/21) | 38% (8/21) |
| gate_drop | 0 | 13 |
| upload_ok | 20 | 7 |
| VLM frames | 20 | 7 |
| T3 压力下降 | — | 65% |
| queue_drop | 0 | 0 |
| 崩溃/OOM | 无 | 无 |

threshold 值为工程占位值，不代表最终检测精度。per-category calibration 留到 Phase 8。

## 10. 已知限制

| 限制 | 影响 | 计划 |
|---|---|---|
| 15 类 raw threshold 未校准 | gate 决策不精确 | Phase 8 |
| FastSAM mask decode 未实现 | 仅 bbox，无像素级分割 | Phase 8+ |
| LoRA 输出质量不稳定 | 1 帧 JSON 失败，重复括号模式 | 模型重训 |
| 4B 模型未验证 | 代码路径存在但回退 2B | Phase 8 |
| 非方形输入 letterbox | 非正方形图片可能变形 | Phase 8+ |
| vision embedding cache | 相同图片重复推理 | Phase 8+ |
| enable_thinking 未评估 | 可能提升 JSON 质量 | Phase 8 |
| description 字段 | T4 JSON 硬编码空值 | 待序列化 |

## 11. Phase 8 计划

1. **Per-category threshold 校准**：全量 MVTec 15 类 raw score 分布分析，确定最优阈值
2. **4 变体 A/B 评估**：2B base / 2B LoRA / 4B base / 4B LoRA 精度与性能对比
3. **节拍优化**：beat_ms 与 VLM 延迟匹配，最小化 drop
4. **求职展示报告**：量化成果、排障故事、工程方法论

## 12. 求职/面试可讲点

> **RK3588 端侧完整闭环**：在 16GB 边缘板上完成四线程异步推理流水线（EfficientAD → FastSAM → Qwen3-VL → Upload → Backend），24 帧 E2E 验收 100% 成功。
>
> **三个关键排障**：（1）EfficientAD post_processor 饱和问题，通过 ONNX trace 定位 raw tensor 并切换 FP16 路线；（2）FastSAM INT8 量化置信度压缩到近零，通过 FP16/no-quant 修复，fallback 从 100% 降至 0%；（3）RKLLM runtime 版本不匹配 + n_image_tokens 语义混淆，通过阅读官方 demo 源码定位。
>
> **观测性与工程验证方法**：设计覆盖型 vs 过滤型对比实验验证 gate 机制，新增 ead_gate_pass/drop 原子计数器区分阈值拦截与队列丢帧，T3 VLM 压力下降 65%。
