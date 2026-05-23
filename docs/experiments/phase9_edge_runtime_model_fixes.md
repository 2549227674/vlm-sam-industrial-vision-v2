# Phase 9：Edge Runtime 与模型链路修复

**日期**：2026-05-24
**分支**：main
**执行者**：Claude Code（CLAUDE_04_EDGE_RUNTIME_AND_MODEL_FIXES.md）

---

## 1. 任务目标

对 RK3588 C++ edge runtime 做最小但关键的稳定性增强：

1. **P1**：修复 Qwen3-VL-4B vision spatial merge（替换 contiguous reshape 为 2x2 permute）
2. **P1**：增强 BoundedQueue 队列与 backpressure 指标
3. **P1**：增加 VLM JSON 输出 watchdog，避免 repeated bracket 长时间阻塞

约束：不做 threshold soak test、calibration split、frontend mock/real badge、FastSAM mask decode。

---

## 2. 修改文件列表

| 文件 | 修改类型 | 说明 |
|---|---|---|
| `edge/include/edge/vlm/qwen3vl_runner.hpp` | 修改 | 添加 `merge_spatial_2x2<T>` 模板函数声明与实现；`VlmResult` 增加 `watchdog_abort` 字段 |
| `edge/include/edge/common/bounded_queue.hpp` | 修改 | 新增 `QueueStats` 结构体（push/pop/drop/high_watermark 原子计数）；`BoundedQueue` 构造函数接受可选 `QueueStats*` |
| `edge/include/edge/common/metrics.hpp` | 修改 | `PipelineMetrics` 新增 `vlm_watchdog_abort`、Q1/Q2/Q3 各 4 个队列指标原子计数器 |
| `edge/include/edge/common/config.hpp` | 修改 | `Config` 新增 4 个 VLM JSON watchdog 配置字段 |
| `edge/src/vlm/qwen3vl_runner.cpp` | 修改 | (a) `run_vision_encoder` 中 4B 路径使用 `merge_spatial_2x2` 替换 contiguous reshape；(b) 新增 `detect_repeated_chars` / `detect_repeated_ngram` watchdog 检测函数；(c) `llm_callback` 中集成 watchdog 逻辑；(d) `infer()` 使用 watchdog 超时替代固定 120s |
| `edge/src/pipeline/fastsam_worker.cpp` | 修改 | VLM 推理后检查 `watchdog_abort` 并递增 `m_.vlm_watchdog_abort`；trace_events 中添加 `vlm_watchdog_abort` 事件 |
| `edge/src/main.cpp` | 修改 | 创建 `QueueStats` 实例并传入 BoundedQueue；新增 `print_queue_stats()` 和周期性（10s）metrics dump；`print_metrics()` 增加 watchdog 和队列统计输出 |
| `edge/src/common/config_loader.cpp` | 修改 | 解析 4 个新增 watchdog 配置字段 |
| `edge/config.yaml` | 修改 | 新增 `vlm_json_watchdog_*` 4 个配置项 |
| `edge/tests/test_qwen3vl_spatial_merge.cpp` | 新建 | 空间合并单元测试（5 个 test case，验证 2x2 permute 正确性） |
| `edge/tests/test_vlm_watchdog.cpp` | 新建 | Watchdog 重复模式检测单元测试（4 个 test case） |

---

## 3. P1-A：4B Vision Spatial Merge 修复（F-VLM-06）

### 3.1 问题描述

4B vision encoder output 为 `[784,1024]`，语义等价于 `[28,28,1024]`。RKLLM 期望 `[196,4096]`（2x2 spatial merge 后的 196 个 image tokens）。

**原错误做法**：contiguous reshape `[784,1024] → [196,4096]`，将 row-major 连续 4 个 token 拼在一起，空间邻域错乱。

**正确做法**：
```
[28,28,1024]
  → reshape [14,2,14,2,1024]
  → permute [14,14,2,2,1024]
  → flatten [196,4096]
```

### 3.2 修复内容

新增 `merge_spatial_2x2<T>` 模板函数（`qwen3vl_runner.hpp`），`run_vision_encoder()` 中当 `needs_spatial_merge_==true` 时对 output[0] 调用此函数，正确地将 2x2 空间邻居分组后展平通道维度。

同时添加 shape/checksum 日志：
```
[Qwen3VL4B] vision_out shape=[784,1024] dtype=fp32(want_float)
[Qwen3VL4B] spatial_merge mode=2x2_permute input_tokens=784 output_tokens=196 embed=4096
[Qwen3VL4B] token_checksum first=... middle=... last=...
```

### 3.3 单元测试

`edge/tests/test_qwen3vl_spatial_merge.cpp` — 5 个 test case：

| 测试 | 内容 | 结果 |
|---|---|---|
| `test_output_size` | 静态断言 196*4096=802816 | PASS |
| `test_first_output_token` | 验证输出 token 0 来自输入 token (0,0), (0,1), (1,0), (1,1) | PASS |
| `test_second_output_token` | 验证输出 token 1 来自输入 token (2,3,30,31) | PASS |
| `test_second_row_first_token` | 验证输出 token 14 来自输入 token (56,57,84,85) | PASS |
| `test_no_data_loss` | 验证全部 784 个输入 token 标记在输出中恰好出现一次 | PASS |

**编译与运行**：`g++ -std=c++20 -O2` x86 编译通过，所有测试 PASS。

---

## 4. P1-B：Queue Runtime Metrics

### 4.1 新增指标

**QueueStats**（`bounded_queue.hpp`）—— 每个队列独立统计：

| 指标 | 类型 | 说明 |
|---|---|---|
| `push_count` | atomic<uint64_t> | push 总次数 |
| `pop_count` | atomic<uint64_t> | pop 总次数 |
| `drop_count` | atomic<uint64_t> | drop-oldest 总次数 |
| `high_watermark` | atomic<uint64_t> | 历史最大深度（CAS 更新） |

**PipelineMetrics**（`metrics.hpp`）—— 新增 13 个计数器：

| 指标 | 说明 |
|---|---|
| `vlm_watchdog_abort` | Watchdog 触发总次数 |
| `q1_push / q1_pop / q1_drop / q1_high_watermark` | Q1 (T1→T2) |
| `q2_push / q2_pop / q2_drop / q2_high_watermark` | Q2 (T2→T3) |
| `q3_push / q3_pop / q3_drop / q3_high_watermark` | Q3 (T3→T4) |

### 4.2 数据流

1. `QueueStats` 在 `main.cpp` 创建，传入 `BoundedQueue` 构造函数
2. `BoundedQueue::push_drop_oldest()` 和 `pop()` 自动更新 stats
3. 主循环每 10 秒 dump 一次周期性 metrics
4. 进程关闭时打印最终 metrics

### 4.3 板端验证

```
--- Queue Stats ---
  Q1 (T1->T2): push=11 pop=11 drop=0 high_watermark=1
  Q2 (T2->T3): push=0 pop=0 drop=0 high_watermark=0
  Q3 (T3->T4): push=0 pop=0 drop=0 high_watermark=0
```

所有 11 帧被 T2 gate 拦截（score=30.14 < threshold=49.17），Q2/Q3 无流量，符合预期。

---

## 5. P1-C：VLM JSON Watchdog

### 5.1 问题

LoRA controlled rerun 中出现 repeated bracket（单帧阻塞约 50s）。即使 LoRA 不作为主线，也需要防护避免任何模型输出退化拖垮 T3。

### 5.2 实现

**CallbackState** 新增字段：
- `watchdog_abort`：是否触发了 watchdog
- `repeated_char_limit` / `repeated_ngram_limit`：阈值

**检测函数**（`qwen3vl_runner.cpp` file-scope static）：
- `detect_repeated_chars()`：检测连续相同字符超过 limit
- `detect_repeated_ngram()`：检测 1-16 字符 n-gram 重复超过 limit

**llm_callback 修改**：每次 `RKLLM_RUN_NORMAL` 回调时：
1. 若已 `watchdog_abort`，直接返回（停止累积文本）
2. 检测 repeated chars 和 n-gram
3. 若触发，设置 `watchdog_abort=true`、`finished=true`、`cv.notify_all()`

**infer() 修改**：
- 超时从固定 120s 改为 `vlm_json_watchdog_max_decode_ms`（默认 45s）
- 结果中传递 `watchdog_abort` 标志

**FastSamWorker 修改**：
- 检查 `vlm_result.watchdog_abort`，递增 `m_.vlm_watchdog_abort`
- trace_events 添加 `vlm_watchdog_abort` 事件

### 5.3 配置（edge/config.yaml）

```yaml
vlm_json_watchdog_enabled: true
vlm_json_watchdog_max_decode_ms: 45000
vlm_json_watchdog_repeated_char_limit: 64
vlm_json_watchdog_repeated_ngram_limit: 32
```

### 5.4 单元测试

`edge/tests/test_vlm_watchdog.cpp` — 4 个 test case：

| 测试 | 内容 | 结果 |
|---|---|---|
| `test_repeated_char_detect` | 检测 64 个相同字符 | PASS |
| `test_repeated_ngram_detect` | 检测 n-gram 重复（1/2/3 字符） | PASS |
| `test_empty_and_short` | 空字符串和短字符串不误报 | PASS |
| `test_mixed_content_with_tail_repetition` | 正常 JSON 后跟括号 spam 能检测 | PASS |

---

## 6. Contract 验证

**执行前基线**：74/74 contract tests passed, no schema drift, frontend typecheck OK
**执行后复查**：74/74 contract tests passed, no schema drift, frontend typecheck OK

本轮修改仅涉及 C++ edge runtime 和 `edge/config.yaml`，不触及 Python backend、前端代码或 API contract schema。contract 完整性未受影响。

---

## 7. F-VLM-06 修复状态

**结论：已修复。**

`docs/ENGINEERING_FINDINGS.md` F-VLM-06 描述的问题（4B vision encoder output contiguous reshape 导致空间邻域错乱）已通过 `merge_spatial_2x2` 函数修复。

修复验证：
- 单元测试 5/5 PASS（包含 2x2 permute 正确性和数据完整性验证）
- 板端编译通过（GCC 11 C++20）
- 板端 smoke test 通过（config 解析、pipeline 初始化、15s 运行无 crash）
- 2B base 主线不受影响（`needs_spatial_merge_=false` 时走原有路径）

**待做**：4B 实际推理回归实验（carpet/tile 等纹理敏感样本验证），需板端加载 4B 模型后运行。

---

## 8. 剩余风险

| 风险 | 严重度 | 说明 |
|---|---|---|
| 4B 推理回归未做 | 中 | 需板端加载 4B 模型运行 carpet/tile 等类别，验证 silent fail 是否消失 |
| Watchdog 仅检测 accumulation 侧 | 低 | RKLLM 推理不会被中止（回调返回 0），仅停止累积文本。RKLLM 线程会自然完成或被 max_new_tokens 截断 |
| QueueStats 无 push_wait / pop_wait | 低 | BoundedQueue 使用 mutex 保护，wait 时间难以准确测量（需 clock 在 mutex 内计时）。当前 push/pop 计数和高水位已足够判断 backpressure |
| threshold soak test 未做 | 中 | 延后至 CLAUDE_05 |
| 4B vlm_variant=lora 未支持 | 低 | 设计限制，init() 返回 false 并报错 |

---

## 9. 编译与运行命令

### 板端编译
```bash
ssh orangepi@192.168.137.66
cd ~/vlm-sam-industrial-vision-v2/edge
rm -rf build && mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build . -j$(nproc)
```

### 板端运行
```bash
cd ~/vlm-sam-industrial-vision-v2/edge
./build/edge_pipeline config.yaml
```

### 本地单元测试（x86）
```bash
cd edge/tests
g++ -std=c++20 -O2 -o test_spatial_merge test_qwen3vl_spatial_merge.cpp && ./test_spatial_merge
g++ -std=c++20 -O2 -o test_vlm_watchdog test_vlm_watchdog.cpp && ./test_vlm_watchdog
```

### Contract 验证
```bash
source .venv/bin/activate
make contract-all
```
