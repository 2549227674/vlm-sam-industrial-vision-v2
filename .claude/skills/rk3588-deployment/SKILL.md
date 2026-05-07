---
name: rk3588-deployment
description: |
  Generates and reviews C++20 edge inference code for the vlm-sam-industrial-vision-v2
  project targeting RK3588 8GB. Use this skill whenever the user mentions RK3588,
  Rockchip NPU, rknn, rkllm, librga, V4L2, dma_buf, EfficientAD-S, FastSAM,
  Qwen3-VL deployment, W8A8 quantization, jthread pipeline, BoundedQueue,
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
- **必须** INT8 / W8A8 量化；量化后必须跑 `accuracy_analysis` 验证 cosine sim > 0.99。
- **必须** 三核 NPU 并行（`rknn_core_num=3`）。
- **必须** KV cache preload 长 system prompt（`rkllm_load_prompt_cache`）。
- **必须** Cache line 对齐 metrics（`alignas(64)`）。
- 错误处理用 `std::expected<T, ErrorCode>`（GCC 13+）或 `tl::expected`（GCC 11/12 fallback）。

## 始终遵守的硬约束（不分场景，12 条）

1. C++ 标准 ≥ C++20；GCC ≥ 11；`#pragma once`；成员变量 trailing underscore（`member_`），struct 公有字段不加。
2. 线程模型固定 4 个：T1 Capture / T2 Pipeline / T3 VLM Worker / T4 Upload，不要新增线程。
3. 所有线程用 `std::jthread`；取消用 `std::stop_token`；CV 等待**必须**用 `std::condition_variable_any` 的三参数 `wait(lock, stop_token, pred)` 重载，**绝不**用 `std::condition_variable`。
4. 句柄类资源（V4L2 fd / RKNN context / RKLLM handle / dma_buf fd）必须 RAII 包装，禁止裸 `int fd`，禁止 `new/delete`。
5. dma_buf fd 单一所有权（`UniqueFd`）；跨线程用 `std::move`；需要共享时用 `dup(fd)`。
6. 队列必须有界 + drop-oldest，必须导出 `dropped_count` 指标，禁止无界队列。
7. libcurl：`curl_global_init` 只在 `main()` 最开头调用一次（所有线程启动前），`HttpClient` 构造函数中**不调用**；每个上传线程独占一个 easy handle，`curl_easy_reset` 复用，禁止每次 init/cleanup。
8. VLM JSON 输出必须经五级 bbox 净化（参考 `edge/src/vlm_bbox_ref.py`）：归一化裁剪 → 面积过滤 → 长宽比过滤 → IoU 去重 → 置信度阈值。此外 `category` 字段值必须做白名单校验 `{"metal_nut", "screw", "pill"}`，非法值丢弃或重置为 `"other"`。
9. 严禁 Base64 传图；严禁在边缘端起 WebSocket 服务；严禁跑 FastAPI / Flask 等 Python Web 框架（8GB 内存压力大）；严禁生成检测报告；严禁 PaDiM 残留。
10. 所有可量化指标（解析失败、上传重试、丢帧、TTFT、tokens/s）写入 `PipelineMetrics` 并通过 `vlm_metrics` 字段上报后端；字段 `alignas(64)` 防 false sharing。
11. EfficientAD-S RKNN 模型输入输出均为 INT8（非 float32），读取 anomaly_map/pred_score 后必须用 `rknn_query(RKNN_QUERY_OUTPUT_ATTR)` 获取量化参数做反量化，禁止直接将 INT8 原始值与浮点阈值比较。
12. FastSAM-s output0（det）和 output1（proto masks）的反量化参数独立，必须分别查询 `RKNN_QUERY_OUTPUT_ATTR` 获取各自的 scale/zero_point，禁止用同一组量化参数处理两路输出。

## 8GB 板特殊约束

- `max_context` 上限 **3072**（不是 4096），否则 KV cache 触顶。
- 单进程共享同一套模型实例（EfficientAD-S + FastSAM + Qwen3-VL-2B）；T1 线程可循环读取 metal_nut / screw / pill 多个类别的图片集模拟多产线节拍，内存占用不变。
- **禁止**开多个独立进程各自加载 VLM——每个 Qwen3-VL-2B 实例占 ~3.1 GB，两个实例直接 OOM。
- 模拟器（Python 多线程多产线）只在 PC 端运行，不在 RK3588 上跑。

## 模型路径

- EfficientAD-S：Anomalib 2.x 训练 → **单一 ONNX** 导出（Teacher/Student/AE 三子网络封装在同一模型中）→ 单个 RKNN INT8 文件。
- Qwen3-VL-2B：HuggingFace → RKLLM W8A8（LLM 路径不经 ONNX）；Vision encoder → RKNN FP16（单独文件）。
- W8A8 是 RK3588 LLM 路径**唯一**支持的量化；W4A16 仅 RK3576 支持，禁止使用。

Qwen3-VL-2B 部署失败时的备选降级顺序与性能数据见 `docs/ARCHITECTURE.md` §3.2，**只改 `edge/config.yaml`，不改 C++ 代码**。
