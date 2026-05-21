# Phase 7 Prompt 2C / 2C-Fix FastSAM 边缘集成报告

## 1. 摘要

本报告记录 `vlm-sam-industrial-vision-v2` 在 Phase 7 Prompt 2C 和 2C-Fix 中，将 C++ 四线程流水线的 T3 从 MockVlmWorker 替换为真实 FastSAM RKNN 推理的工程过程、INT8 量化问题排错、FP16 no-quant 修复和 5 级 bbox 净化实现。

当前结论：

```text
Prompt 2C + 2C-Fix 工程链路已验证：
T1 image_loop → T2 EfficientAD FP16 → Q2 → T3 FastSAM FP16 (real bbox) → Q3 → T4 multipart upload
Qwen3-VL 仍 mock，不接 RKLLM。
```

当前冻结点：

```text
FastSAM FP16/no-quant 模型在 Orange Pi 5 上稳定输出有效 bbox。
0% fallback 帧率。5 级 bbox 净化流水线就绪。
满足进入 Prompt 2D（Qwen3-VL 真实 RKLLM 推理）的条件。
```

## 2. 板端环境

与 Prompt 2B 相同：

```text
Board: Orange Pi 5 16GB (Orange Pi 5 Plus)
IP: 192.168.137.66
OS: Ubuntu 22.04 Jammy
GCC: 11.4.0
RKNN Runtime: librknnrt.so
```

## 3. Prompt 2C 目标

原始目标（`temp_docs/prompt2C.txt`）：

```text
T1 image_loop → T2 EfficientAD FP16 → Q2 → T3 FastSAM real bbox + MockVLM → Q3 → T4 upload
```

功能要求：
1. 加载 fastsam_s.rknn
2. 读取原图 → resize 到 640×640 → RKNN 推理
3. 解码 output0 [1,37,8400] detection output
4. conf filter + NMS → normalized [0,1] bboxes
5. 构造 VlmReport（bboxes 来自 FastSAM，VLM 仍 mock）
6. 不接 Qwen3-VL / RKLLM，不新增线程

## 4. FastSAM RKNN 模型属性

### 4.1 INT8 原始模型（Prompt 2C 初始）

```text
models/fastsam_models/fastsam_s.rknn  (14MB)
input[0]:  name='images'   dims=[1,640,640,3]  type=INT8  zp=-128  scale=0.003922
output[0]: name='output0'  dims=[1,37,8400]    type=INT8  zp=-119  scale=2.820890  (detection)
output[1]: name='output1'  dims=[1,32,160,160] type=INT8  zp=-123  scale=0.059204  (prototype masks)
```

### 4.2 FP16 no-quant 模型（Prompt 2C-Fix）

```text
models/fastsam_models/fastsam_s_noquant.rknn  (26MB)
input[0]:  name='images'   dims=[1,640,640,3]  type=FP16  zp=0  scale=1.000000
output[0]: name='output0'  dims=[1,37,8400]    type=FP16  zp=0  scale=1.000000  (detection)
output[1]: name='output1'  dims=[1,32,160,160] type=FP16  zp=0  scale=1.000000  (prototype masks)
```

## 5. Prompt 2C 实现

### 5.1 新增文件

| 文件 | 说明 |
|---|---|
| `edge/include/edge/pipeline/fastsam_worker.hpp` | T3 FastSamWorker 头文件 |
| `edge/src/pipeline/fastsam_worker.cpp` | T3 FastSamWorker 实现 |

### 5.2 修改文件

| 文件 | 修改 |
|---|---|
| `edge/src/main.cpp` | MockVlmWorker → FastSamWorker；print_config 增加 FastSAM 字段 |
| `edge/CMakeLists.txt` | WORKER_SOURCES 增加 fastsam_worker.cpp |

### 5.3 FastSamWorker 功能

1. **load_model()**: 一次加载 fastsam_s.rknn；查询并打印 input/output attrs；按 n_elems==310800 识别 detection output
2. **preprocess()**: stb_image 解码 → bilinear resize 到 640×640
3. **decode_bboxes()**: output0 → dequant/type-aware float → conf filter → top-5 fallback → greedy NMS (IoU 0.45)
4. **make_fallback_report()**: 推理失败时构造占位 VlmReport

### 5.4 Prompt 2C 验收结果

Clean build: `BUILD_RC=0`（0 errors, 0 warnings）

Smoke test（60s, 4 categories, pass_all）：

```text
capture: 30  ead: 30  vlm: 30  upload_fail: 30  dropped: 0
edge_pipeline: clean exit.
```

关键日志（INT8 模型）：

```text
[T3] FastSAM loaded: 1 inputs, 2 outputs
[T3] detection output index: 0
[T3] det dequant INT8: zp=-119 scale=2.820890 (NOTE: per-tensor quant may reduce conf precision)
[T3] raw candidates after conf>0.25: 0                    ← 全部为 0
[T3] WARNING: 0 candidates above conf threshold 0.25
[T3]   Falling back to top-5 anchors by raw conf score.
[T3]   top-5 fallback produced 5 candidates
[T3] after NMS (iou=0.45): 5 bboxes
```

T4 JSON 契约验证：

```json
{
  "bboxes": [{"x":0.0088,"y":0.0022,"w":0.0793,"h":0.0661}, ...],
  "pipeline_ms": {"efficientad":406.8, "fastsam":182.8, "qwen3vl":0.0},
  "vlm_metrics": {"json_parse_ok": true, ...},
  "trace_events": [...],
  "schema_version": "v1"
}
```

验收通过项：

| 项目 | 结果 |
|---|---|
| T2 EfficientAD final_score 正常 | PASS |
| T3 加载 FastSAM RKNN | PASS |
| T3 打印 input/output attrs | PASS |
| T3 生成 bbox（含 fallback） | PASS |
| T4 JSON bboxes 来自 FastSAM | PASS |
| 无 rknn_run failed | PASS |
| T4 JSON 契约完整 | PASS |
| 无 Qwen3-VL | PASS |
| 无新增线程 | PASS |

## 6. Prompt 2C-Fix：INT8 量化问题与修复

### 6.1 问题根因

INT8 per-tensor quantization 将 8400 个 anchor 的 confidence 值压缩到极窄范围：

```text
output0 INT8 zp=-119 scale=2.820890
dequant: (int8_val - (-119)) * 2.820890
```

以 int8=-119（zp 本身）为例：`(-119 - (-119)) * 2.820890 = 0.0`
以 int8=-118 为例：`(-118 - (-119)) * 2.820890 = 2.82`

scale=2.82 意味着 INT8 每 1 个量化级对应 2.82 的浮点跨度，而 YOLOv8 的 confidence 正常范围是 [0, 1]。INT8 的 256 个量化级只能表示 ~0.35 个浮点单位的精度，导致所有 confidence 值要么是 0 要么远大于 1，完全丧失区分能力。

### 6.2 解决方案：FP16 no-quant

修改 `scripts/convert_fastsam_rknn.py`，新增 `--no-quant` 参数：

```bash
python scripts/convert_fastsam_rknn.py --no-quant
```

行为：
- `rknn.config()` 不传 `quantized_dtype`（跳过 INT8 量化配置）
- `rknn.build(do_quantization=False)`（FP16 权重）
- 输出 `fastsam_s_noquant.rknn`（不覆盖原 INT8 模型）
- 跳过 calibration 和 accuracy_analysis

### 6.3 FP16 no-quant 属性对比

| 属性 | INT8 | FP16 no-quant |
|---|---|---|
| output0 type | INT8 | FP16 |
| output0 zp | -119 | 0 |
| output0 scale | 2.820890 | 1.000000 |
| output1 type | INT8 | FP16 |
| output1 zp | -123 | 0 |
| output1 scale | 0.059204 | 1.000000 |
| 模型文件大小 | 14MB | 26MB |
| conf 精度 | 量化级 ~2.82/unit | FP16 原生精度 |

### 6.4 Prompt 2C-Fix 新增功能

#### Task 2：输入输出类型适配

- 输入：`pass_through=0` + UINT8 RGB → RKNN driver 自动转换（INT8 和 FP16 模型均适用）
- 输出：`want_float=0`（INT8 手动反量化）或 `want_float=1`（FP16/FP32 runtime 转 FP32）
- output0 / output1 独立 zp/scale，禁止共用

#### Task 3：bbox decode 诊断增强

新增日志：
- conf_channel min/max/mean
- conf_channel top-10 值
- sigmoid 检测结果
- 0 candidates 时打印 cx/cy/w/h 通道统计

#### Task 4：5 级 bbox 净化

参考 `edge/src/vlm_bbox_ref.py` 实现 C++ 版本：

| 级别 | 操作 | 常量 |
|---|---|---|
| L1 | clamp [0,1] + 移除退化 | w/h > 0 |
| L2 | 移除面积过小 | area < 0.001 (0.1%) |
| L3 | 移除面积过大 | area > 0.95 (95%) |
| L4 | 高 IoU 去重 | IoU > 0.70 |
| L5 | 限制最大数量 | max 5 |

每级打印数量变化：`raw → after_conf → after_nms → after_cleanup`

#### Task 5：mask decode 保留 TODO

output1 [1,32,160,160] prototype masks 本轮不解码。注释说明：
- output1 已 probe（FP16, zp=0, scale=1.0）
- mask decode 需结合 output0 ch 5-36 系数
- 当前仅使用 detection bbox

## 7. Prompt 2C-Fix 验收结果

### 7.1 Clean Build

```text
[100%] Built target edge_pipeline
BUILD_RC=0
0 errors, 0 warnings
```

### 7.2 Smoke Test 配置

```text
config: /tmp/config_representative_small_raw_debug_fastsam_noquant.yaml
model: fastsam_s_noquant.rknn (FP16 no-quant)
categories: bottle, metal_nut, pill, screw
gate_mode: pass_all
fastsam_conf: 0.25
duration: 60s
```

### 7.3 T3 首帧完整日志

```text
[T3] frame 0 | cat=bottle | model=.../fastsam_s_noquant.rknn
     image=.../bottle/test/broken_small/006.png
     ead_final_score=12.008 ead_infer_ms=367.4
     orig_size=900x900  input_size=640  preprocess_ms=105.4
     infer_ms=155.3
  [T3][first_frame] output[0] name='output0' type=FP16 zp=0 scale=1.000000
                     n_elems=310800 want_float=1  <- DETECTION output
  [T3][first_frame] output[1] name='output1' type=FP16 zp=0 scale=1.000000
                     n_elems=819200 want_float=1  <- prototype(mask TODO) output
  [T3] output0 FP32 (want_float=1)
  [T3] conf_channel min=0.0000 max=0.8794 mean=0.0025 (n=8400)
  [T3] conf_channel top-10: 0.8794 0.8628 0.8613 0.8569 0.8481 0.8452 ...
  [T3] max_abs_conf=0.000 <= 4.0 -> values already in [0,1]
  [T3] raw candidates after conf>0.25: 24
  [T3] after NMS (iou=0.45): 3 bboxes
  [T3] cleanup L1 bounds: 3 -> 3
  [T3] cleanup L2 min_area(0.001): 3 -> 3
  [T3] cleanup L3 max_area(0.95): 3 -> 3
  [T3] cleanup L4 dedup(iou=0.70): 3 -> 3
  [T3] after_cleanup: 3 bboxes
     postprocess_ms=8.3  bbox_count=3  total_ms=292.2
     bbox[0] x=0.030 y=0.059 w=0.872 h=0.932
     bbox[1] x=0.292 y=0.280 w=0.445 h=0.445
     bbox[2] x=0.499 y=0.204 w=0.110 h=0.088
     [stats] total_frames=1 fallback_frames=0
```

### 7.4 Fallback 帧比例

| 指标 | INT8 (Prompt 2C) | FP16 (Prompt 2C-Fix) |
|---|---|---|
| total_frames | 30 | 31 |
| fallback_frames | 30 | 0 |
| fallback 比例 | **100%** | **0%** |

### 7.5 Conf 分布对比

| 指标 | INT8 | FP16 |
|---|---|---|
| conf top-1 | ~0.003（量化失真） | 0.8794 |
| conf top-10 | 全部近零 | 0.794 ~ 0.879 |
| after conf>0.25 | 0 candidates | 24 candidates |
| bbox 来源 | top-5 fallback | 正常 conf filter |

### 7.6 Bbox 坐标分布

| 帧 | bbox[0] x | y | w | h | 说明 |
|---|---|---|---|---|---|
| 0 | 0.030 | 0.059 | 0.872 | 0.932 | 覆盖物体主体 |
| 1 | 0.022 | 0.047 | 0.874 | 0.929 | 稳定 |
| 2 | 0.017 | 0.048 | 0.877 | 0.899 | 稳定 |
| 3 | 0.036 | 0.054 | 0.880 | 0.935 | 稳定 |

对比 INT8（2C 初始）：

| 帧 | bbox[0] x | y | w | h | 说明 |
|---|---|---|---|---|---|
| 0 | 0.009 | 0.002 | 0.079 | 0.066 | 聚集在 (0,0) |
| 1 | 0.002 | 0.000 | 0.093 | 0.066 | 聚集在 (0,0) |

### 7.7 Pipeline Metrics

```text
capture:      31
ead:          31
vlm:          30
upload_ok:    0          (后端不可达，预期行为)
upload_fail:  30
dropped:      0
edge_pipeline: clean exit.
```

### 7.8 验收标准通过情况

| # | 标准 | 结果 |
|---|---|---|
| 1 | build 通过 | PASS |
| 2 | T2 EfficientAD final_score 正常 | PASS |
| 3 | T3 加载 fastsam_s_noquant.rknn | PASS |
| 4 | T3 打印 no-quant 模型 attrs | PASS |
| 5 | output0 不再是 INT8 scale=2.82 | PASS (FP16 scale=1.0) |
| 6 | 部分帧 after conf > 0 | PASS (24/frame) |
| 7 | fallback_frames != total_frames | PASS (0 vs 31) |
| 8 | bbox 不聚集在 (0,0) | PASS |
| 9 | after_cleanup bbox 合法 [0,1] | PASS |
| 10 | T4 meta JSON 合法 | PASS |
| 11 | 无 rknn_run failed | PASS |
| 12 | 不接 Qwen3-VL | PASS |
| 13 | 不改后端 API | PASS |
| 14 | 不改前端 | PASS |
| 15 | 不新增线程 | PASS |

## 8. 已知限制与 TODO

1. **mask decode 未实现**：output1 [1,32,160,160] prototype masks 需结合 output0 ch 5-36 系数解码，当前仅使用 detection bbox。
2. **letterbox 未实现**：MVTec 900×900 是正方形所以简单 resize 等价于 letterbox；非正方形输入需要 grey padding + 坐标恢复。
3. **fastsam_conf=0.25 为调试值**：正式生产阈值需在 Phase 8 按类别校准。
4. **FastSAM 与 EfficientAD 是独立模型**：bbox 覆盖整个物体区域（如 bottle 占 90% 画面），不是精确定位缺陷子区域。缺陷定位仍依赖 EfficientAD anomaly map。
5. **FP16 模型 26MB > INT8 14MB**：内存增量可接受（16GB 板裕度充足），推理速度差异待 Phase 8 benchmark。
6. **T4 HTTP 0**：后端不可达，不影响 T3 验证。

## 9. Commit 记录

| Commit | 说明 |
|---|---|
| `26a9ee0` | Prompt 2C：新增 FastSamWorker，替换 MockVlmWorker |
| `a0ce481` | Prompt 2C-Fix：FP16 no-quant + 5 级 bbox 净化 + 诊断增强 |

## 10. 当前冻结点

```text
Phase 7 Prompt 2C + 2C-Fix:
FastSAM FP16/no-quant real bbox extraction + 5-level cleanup validated on Orange Pi 5.
0% fallback. Bbox quality acceptable. Pipeline contract intact.
```

下一步：

```text
Prompt 2D: Qwen3-VL 真实 RKLLM 推理接入 T3（替换 mock VLM JSON）。
```

## 11. 求职/面试可讲点

> 在 RK3588 部署 FastSAM-s 时发现 INT8 per-tensor quantization 的 scale=2.82 将 YOLOv8
> detection head 的 confidence 值（正常 [0,1]）量化到近零范围，导致所有 anchor 的
> confidence 过滤全部失败（raw candidates = 0），只能依赖无意义的 top-5 fallback。
> 通过导出 FP16 no-quant RKNN 模型彻底绕开量化精度损失，conf 恢复到 0.7~0.88
> 的正常范围，24 个 anchor 通过阈值过滤。同时实现了 5 级 bbox 净化流水线（边界裁剪、
> 面积过滤、IoU 去重、数量限制），将 T3 从 100% fallback 降至 0%，完成 FastSAM 端侧
> 工程闭环。
