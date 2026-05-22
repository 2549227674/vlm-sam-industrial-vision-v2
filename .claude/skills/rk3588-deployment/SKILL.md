---
name: rk3588-deployment
description: |
  Generates and reviews C++20 edge inference code for the vlm-sam-industrial-vision-v2
  project targeting RK3588 16GB. Use this skill whenever the user mentions RK3588,
  Rockchip NPU, rknn, rkllm, librga, V4L2, dma_buf, EfficientAD-S, FastSAM,
  Qwen3-VL-2B, Qwen3-VL-4B, LoRA deployment, W8A8 quantization, jthread pipeline, BoundedQueue,
  libcurl multipart upload, or zero-copy inference — even without the word "deployment".
allowed-tools: Bash(cmake *), Bash(make *), Bash(scp *), Bash(ssh *)
license: Internal-CourseProject
---

# RK3588 Deployment Skill

## 何时使用本 Skill

只要任务涉及以下任一关键词，就**主动**激活本 Skill：

- 边缘端 / RK3588 / Rockchip / NPU / aarch64
- `librknnrt` / `librkllmrt` / `librga` / V4L2 / dma_buf
- 三段式流水线 / 异步推理 / `std::jthread` / `std::stop_token`
- BoundedQueue / drop-oldest / 背压
- `libcurl` multipart / `curl_mime_*`
- EfficientAD-S / FastSAM / Qwen3-VL-2B / W8A8 / INT8 量化
- KV cache preload / `rkllm_load_prompt_cache`

即使用户只问「怎么写一个上传函数」，只要上下文是本项目，也按本 Skill 的约束生成。

代码模板（BoundedQueue、UniqueFd、libcurl HttpClient、Worker）见 `docs/ARCHITECTURE.md` §11，本文件只做行为引导。

## 开发阶段

**轨道 B（C++ RK3588 推理流水线）板子到货后直接按性能版开发，无原型阶段。**

所有 C++ 代码从一开始就按以下标准：

- **必须** V4L2 + dma_buf 零拷贝（`importbuffer_fd` → `rknn_create_mem_from_fd`）。
- **必须** INT8 / W8A8 量化；量化后必须跑 `accuracy_analysis` 验证 cosine sim > 0.99。已知例外：FastSAM output1（proto masks）cosine=0.966，此为已知精度损失，**不得因此判定转换失败**，需上板人工确认分割质量。
- **必须** 三核 NPU 并行（`rknn_core_num=3`）。
- **必须** KV cache preload 长 system prompt（`rkllm_load_prompt_cache`）。
- **必须** Cache line 对齐 metrics（`alignas(64)`）。
- 错误处理用 `std::expected<T, ErrorCode>`（GCC 13+）或 `tl::expected`（GCC 11/12 fallback）。

## 始终遵守的硬约束（不分场景，15 条）

1. C++ 标准 ≥ C++20；GCC ≥ 11；`#pragma once`；成员变量 trailing underscore（`member_`），struct 公有字段不加。
2. 线程模型固定 4 个：T1 Capture / T2 Pipeline / T3 VLM Worker / T4 Upload，不要新增线程。
3. 所有线程用 `std::jthread`；取消用 `std::stop_token`；CV 等待**必须**用 `std::condition_variable_any` 的三参数 `wait(lock, stop_token, pred)` 重载，**绝不**用 `std::condition_variable`。
4. 句柄类资源（V4L2 fd / RKNN context / RKLLM handle / dma_buf fd）必须 RAII 包装，禁止裸 `int fd`，禁止 `new/delete`。
5. dma_buf fd 单一所有权（`UniqueFd`）；跨线程用 `std::move`；需要共享时用 `dup(fd)`。
6. 队列必须有界 + drop-oldest，必须导出 `dropped_count` 指标，禁止无界队列。
7. libcurl：`curl_global_init` 只在 `main()` 最开头调用一次（所有线程启动前），`HttpClient` 构造函数中**不调用**；每个上传线程独占一个 easy handle，`curl_easy_reset` 复用，禁止每次 init/cleanup。
8. VLM JSON 输出必须经五级 bbox 净化（参考 `edge/src/vlm_bbox_ref.py`）：归一化裁剪 → 面积过滤 → 长宽比过滤 → IoU 去重 → 置信度阈值。此外 `category` 字段值必须做白名单校验 `{"bottle","cable","capsule","carpet","grid","hazelnut","leather","metal_nut","pill","screw","tile","toothbrush","transistor","wood","zipper"}`（全 15 类，执行前先 `ls simulator/mvtec/` 确认实际目录名），非法值丢弃或重置为 `"other"`。
9. 严禁 Base64 传图；严禁在边缘端起 WebSocket 服务；严禁跑 FastAPI / Flask 等 Python Web 框架；严禁生成检测报告；严禁 PaDiM 残留。
10. 所有可量化指标（解析失败、上传重试、丢帧、TTFT、tokens/s）写入 `PipelineMetrics` 并通过 `vlm_metrics` 字段上报后端；字段 `alignas(64)` 防 false sharing。
11. EfficientAD-S RKNN 模型输入输出均为 INT8（非 float32），读取 anomaly_map/pred_score 后必须用 `rknn_query(RKNN_QUERY_OUTPUT_ATTR)` 获取量化参数做反量化，禁止直接将 INT8 原始值与浮点阈值比较。
12. FastSAM-s output0（det）和 output1（proto masks）的反量化参数独立，必须分别查询 `RKNN_QUERY_OUTPUT_ATTR` 获取各自的 scale/zero_point，禁止用同一组量化参数处理两路输出。
13. Qwen3-VL-4B 视觉 encoder 版本选择：优先使用 v1.2.2 视觉 .rknn（~670 MB），混搭 v1.2.3 runtime。v1.2.3 视觉文件（~827 MB）存在精度回退（Issue #421），仅作备用。
14. Qwen3-VL-4B 内存约束：运行时 RAM ~8.7 GB（含 KV cache ctx=4096），Pipeline 总峰值 ~11.4 GB，16GB 板裕度 ~3.1 GB。**禁止**同时加载 2B 和 4B 实例。
15. **Qwen3.5 系列已确认排除**：rknn-llm Issue #472，Gated DeltaNet 架构不被 rknn-llm v1.2.3 支持。任何文档和代码中不得将 Qwen3.5 作为候选项。

## 16GB 板约束（实际硬件）

- `max_context` 上限 **4096**。
- 单进程共享同一套模型实例（EfficientAD-S + FastSAM + Qwen3-VL-2B/4B）；T1 线程可循环读取多个类别的图片集模拟多产线节拍，内存占用不变。
- **禁止**开多个独立进程各自加载 VLM——每个 Qwen3-VL-2B 实例占 ~3.1 GB（4B ~8.7 GB），多个实例会快速消耗内存。含 4B 时 Pipeline 总峰值约 11.4 GB，裕度 ~3.1 GB；**禁止**同时加载 2B 和 4B。
- 模拟器（Python 多线程多产线）只在 PC 端运行，不在 RK3588 上跑。

## 模型路径

- EfficientAD-S：Anomalib 2.x 训练 → **单一 ONNX** 导出（Teacher/Student/AE 三子网络封装在同一模型中）→ 单个 RKNN INT8 文件。
- Qwen3-VL-2B：HuggingFace → RKLLM W8A8（LLM 路径不经 ONNX）；Vision encoder → RKNN FP16（单独文件）。
- Qwen3-VL-4B：直接使用 Qengineering 预转换文件（**不自行转换 base 文件**，Issue #388 自转失败率高）。
  - `.rkllm` 文件 ~4.51 GB，Vision `.rknn` ~670 MB（v1.2.2）/ ~827 MB（v1.2.3，精度有回退）
  - 来源：`https://github.com/Qengineering/Qwen3-VL-4B-NPU`（Sync.com 镜像，总 5.4 GB）
  - 推荐混搭：**v1.2.2 视觉 .rknn + v1.2.3 runtime**（Issue #421 社区共识）
- W8A8 是 RK3588 LLM 路径**唯一**支持的量化；W4A16 仅 RK3576 支持，禁止使用。
- **Qwen3.5 系列已确认排除**：rknn-llm Issue #472，Gated DeltaNet 架构不被 rknn-llm v1.2.3 支持。

Qwen3-VL 部署失败时的备选降级顺序与性能数据见 `docs/ARCHITECTURE.md` §3.2，**只改 `edge/config.yaml`，不改 C++ 代码**。已排除 Qwen3.5（rknn-llm #472，Gated DeltaNet 不支持）。

## EfficientAD Phase 7 Prompt 2B 约束

- 不依赖 Anomalib post_processor 输出 `pred_score/anomaly_map` 作为 T2 gate。
- 使用 post_processor 前的 raw 输出：
  - `raw_score`（`/model/ReduceMax_output_0`）
  - `raw_anomaly_map`（`/model/Add_output_0`）
- 当前主路线为 FP16/no-quant raw RKNN：
  - `model_raw_noquant.rknn`
- raw INT8 RKNN 在 Prompt 2B 板端测试中显示分布失真，不得作为默认 T2 路径。
- T2 必须支持 `efficientad_score_mode`：
  - raw_score / map_max / map_mean / map_top1 / map_top01
- T2 必须支持 `efficientad_gate_mode`：
  - threshold（正式默认）
  - pass_all（仅调试）
- `pass_all` 是 DEBUG-ONLY，不代表正式产线节拍。
- 正式配置默认使用 `efficientad_gate_mode: threshold`。
- 调试配置可使用 `efficientad_gate_mode: pass_all`。
- 旧阈值 `0.50` 不适用于 raw EfficientAD 输出。per-category raw threshold 需后续校准。
- FP16 RKNN 输出不要按 INT8 解析，应通过 output attr type 判断，使用 `want_float=1`。

## Prompt-only / OPRO 与 RKLLM 部署链路的关系

**Prompt-only baseline 和 OPRO 优化不进入 RKLLM 模型转换链路**。这些方法仅作为 PC 阶段的方法学对照实验，用于量化 prompt engineering 的单独贡献和 LoRA 微调的真实收益。

RKLLM 部署链路只处理以下产出：
- `models/qwen3vl_lora_adapter_15cls/` → LLaMA-Factory export → RKLLM W8A8（2B LoRA）
- `models/qwen3vl_lora_4b_adapter/` → LLaMA-Factory export → RKLLM W8A8（4B LoRA）
- 社区预转换的 base .rkllm 文件

OPRO 搜索出的最优 prompt 可以在 C++ 代码中硬编码为 system prompt，但 prompt 优化过程本身（迭代搜索、LLM 评估）只在 PC 端完成。

## Phase 8 新增约束

- EfficientAD score mode 必须使用 `raw_score`（ReduceMax 输出），不使用 `map_mean`（被背景区域稀释，AUROC 更低）。5 种 mode 实测 mean AUROC：raw_score 0.5320 > map_mean 0.4561。

- T2 EfficientAD gate 在当前 raw output 下定位为**负载脱落门控（load shedding gate）**，不是精确检测分类器。全 15 类 AUROC < 0.80（best: tile 0.8193）。设置 good_p95 阈值意味着约 5% good 帧进入 T3，大量 defect 帧被误 drop。

- beat_ms 设计公式（实测验证）：
  ```
  安全 beat_ms >= VLM_avg_ms / 0.85
  2B base pass_all：推荐 13000ms，最小稳定 10000ms
  4B base pass_all：推荐 >=35000ms
  ```

- 4B vision encoder 需要 spatial patch merge 处理：
  output[0] 维度 [784, 1024]，需 reshape 为 [196, 4096]（embed_dim = 1024 × 4）。
  n_image_tokens = 196（patch_h=14, patch_w=14），非 784。
  正确做法：`[28,28,1024] → permute[14,2,14,2,1024] → [196,4096]`。
  当前 contiguous reshape 对 6/7 类别有效，carpet 触发静默失败。

- W8A8 量化破坏 LoRA 细粒度分类能力：
  PC bf16 defect_type_exact = 51.8%，board W8A8 = 0%。
  根因：LoRA rank-32 delta 幅值小于 W8A8 量化分辨率，delta 被量化为零。
  category_exact 不受影响（粗粒度知识，量化鲁棒）。
  结论：RK3588 LLM 路径（W8A8 only）不适合 LoRA 部署。

- 禁止在 pass_all 模式下把 beat_ms 设置为低于 VLM_avg_ms 的值，否则 Q2（capacity=2）会溢出并产生 queue_drop。反压会引发 VLM 延迟放大（beat=5000ms 实测 VLM avg 增加 21.9%）。

- per-category threshold 全部使用 raw_score good_p95（Phase 8A-Fix-Fix 后校准）。混合不同 score mode 的阈值是错误的，因为运行时应用单一全局 score_mode。
