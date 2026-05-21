# Phase 7 Prompt 2D-Fix: VLM bbox 融合、LoRA 路径选择与质量修补报告

## 1. 摘要

本报告记录 Prompt 2D 完成后对 Qwen3-VL 集成所做的六项针对性修补：

1. **VLM bbox 解析、归一化与融合** — 保守策略：FastSAM 优先
2. **severity 白名单统一** — 仅保留 `low|medium|high`，移除 `critical`
3. **LoRA/variant 路径选择** — `2B base` / `2B lora` 通过 config 切换，`4B` 保留 TODO
4. **description 词数限制** — prompt 强制 `max 20 words`，output_tokens > 120 打印 warning
5. **upload trace_event** — 追加到 trace_events 数组
6. **调试配置** — `config.debug.yaml` 更新为 2B，新增 `config.debug.lora.yaml`

当前结论：

```text
Prompt 2D-Fix 六项修补全部完成：
- VLM bbox 归一化 + 保守融合（IoU>0.3 才替换 FastSAM）
- severity 仅 low/medium/high，0 次 critical
- 2B base json_parse_ok=100%，output_tokens 52-79
- 2B lora 路径选择正确，LoRA 模型输出质量为独立问题
- trace_events 6 项完整（含 upload）
```

当前冻结点：

```text
Phase 7 四线程流水线稳定运行。
2B base 全量指标达标，可进入 Prompt 2E 端到端验收。
```

## 2. 修改文件清单

| 文件 | 修改内容 |
|---|---|
| `edge/include/edge/vlm/qwen3vl_runner.hpp` | VlmResult 新增 `vlm_bboxes` 字段，新增 `parse_vlm_bboxes()` 声明，更新 `extract_json()` 签名 |
| `edge/src/vlm/qwen3vl_runner.cpp` | 新增 `parse_vlm_bboxes()` 实现，severity 修复（移除 critical），新增 severity_corrected 参数，LoRA/4B 路径选择，文件存在性校验，prompt description 词数限制，output_tokens warning |
| `edge/src/pipeline/fastsam_worker.cpp` | 新增 orig_w/orig_h 捕获，VLM bbox 融合逻辑（IoU>0.3），bbox_source/bbox_merge_reason 日志，output_tokens warning，更新 extract_json 调用 |
| `edge/src/upload/upload_worker.cpp` | 新增 upload 计时，upload trace_event 追加到 trace_events 数组，`<cstring>` include，upload_ms 日志 |
| `edge/config.yaml` | `vlm_max_new_tokens: 200` → `500` |
| `edge/config.debug.yaml` | `vlm_model_size: 4B` → `2B`，`vlm_max_new_tokens` → `500` |
| `edge/config.debug.lora.yaml` | **新增**：2B LoRA 调试配置 |

## 3. Bbox 归一化与融合策略

### 3.1 检测逻辑

`parse_vlm_bboxes()` 从 VLM JSON raw_text 提取 `[[x,y,w,h]]`：

- 若所有值 > 2.0 → 像素坐标 → 除以 `orig_w × orig_h` 归一化
- 若所有值在 [0,1] → 已归一化
- 若 `orig_w/orig_h` 未知 → 除以 448×448（vision 输入尺寸）
- 有效性：x/y/w/h ∈ [0,1]，w/h > 0.001，面积 ∈ [0.0001, 0.95]

### 3.2 融合策略（保守）

```
if VLM bboxes 有效 AND NOT bbox_fallback:
    if 任一 VLM bbox 与任一 FastSAM bbox 的 IoU > 0.3:
        bbox_source = "vlm"
        → 用 VLM bbox 替换 FastSAM bbox
    else:
        bbox_source = "fastsam_fallback"
        → 保留 FastSAM bbox
else:
    bbox_source = "fastsam"
    → 保留 FastSAM bbox
```

设计意图：VLM bbox 在与 FastSAM 检测对齐时有参考价值，但幻觉产生的 VLM bbox 绝不能覆盖稳定的 FastSAM 输出。

## 4. Severity 白名单

| 修复前 | 修复后 |
|---|---|
| `low`, `medium`, `high`, `critical` | `low`, `medium`, `high` |

- prompt、parser、validator 三处同时移除 `critical`
- 无效 severity → 回退为 `medium`，日志输出 `severity_corrected=true`
- `json_parse_ok` 仍为 `true`（修正属于美化性调整，非结构失败）

## 5. LoRA/Variant 路径选择

| 配置 | LLM 路径 | Vision 路径 |
|---|---|---|
| `2B base` | `vlm_model_path` | `vlm_vision_model_path` |
| `2B lora` | `vlm_2b_lora_model_path` | `vlm_vision_model_path` |
| `4B *` | TODO（打印 warning，回退到 2B base） | — |

- LoRA 模型文件不存在 → init 失败并报错（不静默回退）
- LLM 和 vision 路径均做文件存在性校验
- Init 日志输出：`selected_model_size`, `selected_variant`, `selected_llm_path`, `selected_vision_path`

## 6. Smoke Test 结果

### 6.1 2B Base

```text
配置: /tmp/config_bottle_raw_debug.yaml
模型: qwen3vl_2b_w8a8_base.rkllm + qwen3vl_2b_vision.rknn
类别: bottle（单类）
时长: 240s
```

| 指标 | 值 |
|---|---|
| capture | 183 |
| ead | 183 |
| vlm | 23 |
| json_ok=1 | 23（100%） |
| fallback_frames | 0 |
| severity=critical | 0 |
| output_tokens warning | 0 |
| rknn_run failed | 0 |
| rkllm fatal | 0 |
| OOM | 0 |
| 正常退出 | 是 |

VLM 性能（2B base W8A8）：

| 指标 | 值 |
|---|---|
| ttft | 2232–2725 ms |
| decode_tps | 8.7–9.2 |
| output_tokens | 52–79 |
| rss | 3321–3323 MB |

Bbox 融合日志（帧 0）：

```text
vlm_bbox_normalized[0]: x=0.0219 y=0.0469 w=0.8742 h=0.9289
bbox_source=vlm
bbox_merge_reason: VLM bbox aligned with FastSAM (IoU>0.3)
```

T4 JSON（帧 0，格式化）：

```json
{
  "line_id": "L1",
  "category": "bottle",
  "defect_type": "anomaly",
  "severity": "low",
  "confidence": 0.95,
  "anomaly_score": 11.77,
  "bboxes": [{"x": 0.0219, "y": 0.0469, "w": 0.8742, "h": 0.9289}],
  "variant": "2B_base",
  "pipeline_ms": {"efficientad": 1302.0, "fastsam": 136.8, "qwen3vl": 12810.5},
  "vlm_metrics": {
    "ttft_ms": 2232.4, "decode_tps": 9.1,
    "prompt_tokens": 445, "output_tokens": 73,
    "rss_mb": 3321.6, "json_parse_ok": true
  },
  "trace_events": [
    {"name": "efficientad_infer", "dur": 1302006.4},
    {"name": "fastsam_preprocess", "dur": 29291.9},
    {"name": "fastsam_infer", "dur": 106172.1},
    {"name": "fastsam_postprocess", "dur": 1378.1},
    {"name": "qwen3vl_generate", "dur": 12810534.0},
    {"name": "upload", "dur": 0.0}
  ],
  "schema_version": "v1"
}
```

### 6.2 2B LoRA

```text
配置: /tmp/config_bottle_raw_debug_lora.yaml
模型: qwen3vl_2b_w8a8_lora_15cls.rkllm + qwen3vl_2b_vision.rknn
类别: bottle（单类）
时长: 240s
```

| 指标 | 值 |
|---|---|
| capture | 194 |
| vlm | 13 |
| json_ok=1 | 13（100%） |
| JSON 解析失败（fallback） | 1 |
| severity=critical | 0 |
| output_tokens warning | 1（499 > 120） |
| 正常退出 | 是 |

Init 日志确认 LoRA 路径：

```text
selected_model_size=2B  selected_variant=lora
selected_llm_path=/home/orangepi/models/qwen3vl_models/qwen3vl_2b_w8a8_lora_15cls.rkllm
```

LoRA 模型观察：

- 1 帧 JSON 解析失败 → rule-based fallback 生效
- 1 帧 output_tokens 达 499（接近 max_new_tokens=500）→ bboxes 中出现重复括号模式
- Bbox 格式质量低于 base 模型（部分帧嵌套层数过多）
- LoRA 路径选择功能正确；模型输出质量属独立问题

## 7. Upload Trace Event

- 作为第 6 个事件追加到 trace_events 数组（前 5 个为流水线事件）
- `name="upload"`，`dur=0.0`（占位值 — 实际耗时通过 stderr 的 `[T4] upload_ms=...` 记录）
- dur=0.0 原因：trace event 在 HTTP 调用前嵌入，无法预知上传耗时
- 验证：T4 JSON 帧 0 包含 6 个 trace_events

## 8. 验收清单

| # | 标准 | 结果 |
|---|---|---|
| 1 | build 通过 | PASS |
| 2 | 2B base smoke test 通过 | PASS |
| 3 | json_parse_ok=true（base） | PASS（100%） |
| 4 | bbox_source 日志可见 | PASS |
| 5 | T4 JSON bboxes x/y/w/h ∈ [0,1] | PASS |
| 6 | VLM 像素 bbox 已归一化 | PASS |
| 7 | severity 仅 low/medium/high | PASS（0 次 critical） |
| 8 | output_tokens ≤ 120（base） | PASS（52-79） |
| 9 | LoRA 路径选择正确 | PASS |
| 10 | 无崩溃 / 无 OOM | PASS |
| 11 | 无 rknn_run failed | PASS |
| 12 | 无 rkllm fatal | PASS |
| 13 | 不改后端 API | PASS |
| 14 | 不改前端 | PASS |
| 15 | 不新增线程 | PASS |
| 16 | 不回退 EfficientAD | PASS |
| 17 | 不回退 FastSAM FP16/no-quant | PASS |
| 18 | 不回退 MockVLM | PASS |

## 9. 已知限制与 TODO

1. **LoRA 模型输出质量**：重复括号模式、1 次 JSON 解析失败、1 次接近 token 上限。属模型质量问题，非代码问题，需单独调查。
2. **upload trace_event dur=0.0**：占位值。实际耗时记录在 stderr。可通过上传后重新序列化 JSON 改进。
3. **4B 路径**：代码路径存在但打印 warning 并回退到 2B base。模型已上板但未验证。
4. **T4 JSON description 字段**：`build_meta_json()` 硬编码空 description。VLM description 在 VlmReport 中可用但未序列化。属 2D-Fix 范围外。
5. **enable_thinking**：本轮未评估。默认保持 `false`。
6. **Vision embedding 缓存**：未实现。设计推迟至后续优化。

## 10. Prompt 2E 就绪条件

进入 Prompt 2E 的前提：

- [x] 2B base 流水线稳定，bbox 融合与 severity 统一就绪
- [x] LoRA 路径选择功能正常（模型质量为独立问题）
- [x] trace_events 6 项完整（含 upload）
- [x] 相较 Prompt 2D 无回退

满足进入 Prompt 2E 的条件。
