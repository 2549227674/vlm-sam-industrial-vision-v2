# Phase 7 Prompt 2B EfficientAD 边缘集成报告

## 1. 摘要

本报告记录 `vlm-sam-industrial-vision-v2` 在 Phase 7 Track B / Prompt 2B 中，将 C++ 四线程流水线的 T2 从 MockPipelineWorker 替换为真实 EfficientAD-S RKNN 推理的工程过程、排错路径、关键数据和结论。

当前结论：

```text
Prompt 2B 工程链路已验证：
raw ONNX → FP16/no-quant raw RKNN → Orange Pi 5 → C++ T2 FP16 output parse → score_mode/gate_mode → MockT3 → T4
```

当前冻结点：

```text
代表类 bottle / metal_nut / pill / screw 的 FP16/no-quant raw RKNN 工程验证通过。
下一步：批量 15 类 FP16/no-quant raw RKNN 转换、上传和 smoke test，然后进入 Prompt 2C。
```

## 2. 板端环境

实际使用环境：

```text
Board: Orange Pi 5 16GB
Storage: NVMe 128G
IP: 192.168.137.66
OS: Ubuntu 22.04 Jammy
Kernel: 6.1.99-rockchip-rk3588
RKNPU driver: v0.9.8
GCC: 11.4.0
CMake: 3.22.1
Runtime libraries:
  /usr/lib/librknnrt.so
  /usr/lib/librkllmrt.so
  /usr/lib/librga.so
  /usr/lib/aarch64-linux-gnu/libcurl.so
```

板端已具备真实 RKNN/RKLLM/RGA 头文件与动态库。Prompt 1 阶段曾确认 CMake 能找到真实库：

```text
-- Found rknnrt: /usr/lib/librknnrt.so
-- Found rkllmrt: /usr/lib/librkllmrt.so
-- Found rga: /usr/lib/librga.so
-- Found CURL: /usr/lib/aarch64-linux-gnu/libcurl.so
```

## 3. Prompt 1 / Prompt 2A 基础状态

### Prompt 1

完成内容：

- `edge/CMakeLists.txt`
- config loader
- http client
- C++ foundation main
- 真实库优先，stub 仅 fallback
- 板上 clean build 通过

### Prompt 2A

完成内容：

- T1 CaptureWorker：image_loop
- MockPipelineWorker
- T4 UploadWorker
- main.cpp 四线程串联
- curl_global_init / cleanup
- SIGINT / SIGTERM graceful shutdown

验证结果：

```text
[T1] scanned 1725 images across 15 categories
[T4] meta JSON generated
Prompt 2A mock pipeline runs on Orange Pi 5
```

## 4. Prompt 2B 初始目标

原始目标：

```text
T1 image_loop → T2 EfficientAD-S RKNN → Q2 → MockT3 → T4 multipart upload
```

T2 预期行为：

1. 按 category lazy load EfficientAD RKNN。
2. 图像 resize 到 256×256。
3. RKNN 推理输出 anomaly score。
4. `score > threshold` 时推入 Q2。
5. `score <= threshold` 时 drop。

## 5. 问题一：post_processor / Greater 导致 RKNN Runtime 失败

旧模型输出包含：

```text
pred_score
pred_label
anomaly_map
pred_mask
```

板端 `rknn_run` 报错：

```text
ElementwiseLogical: unsupported A type: INT8, B type: FLOAT
Op type: Greater, name: Greater:/post_processor/Greater_1
[T2] rknn_run failed: -1
```

原因分析：

- `pred_label / pred_mask` 是 post_processor 后的阈值比较结果。
- RKNN Runtime 对 INT8 tensor 与 FLOAT threshold 的 `Greater` 支持异常。
- 即使 C++ 不读取 `pred_label/pred_mask`，`rknn_run` 仍执行整张图，因此仍然失败。

阶段性处理：

- 尝试只导出 `pred_score/anomaly_map`。
- 该操作绕开 `Greater`，但暴露出 score 饱和问题。

## 6. 问题二：pred_score / anomaly_map 是 post_processor 后输出

ONNX Runtime 直接测试发现：

```text
train/good pred_score ≈ 0.91 ~ 1.00
test/good pred_score ≈ 0.90 ~ 1.00
test/defect pred_score ≈ 0.97 ~ 1.00
```

这说明 `pred_score` 不能区分 good/defect。

ONNX trace 结果：

```text
pred_score
<- Clip
   <- Add
      <- Div
         <- Sub
            <- /model/ReduceMax_output_0
            <- post_processor._image_threshold

anomaly_map
<- Clip
   <- Add
      <- Div
         <- Sub
            <- /model/Add_output_0
            <- post_processor._pixel_threshold
```

结论：

```text
pred_score/anomaly_map 是 post_processor 归一化 + Clip 后输出，不适合端侧 raw threshold gate。
```

## 7. 解决方案：导出 raw ONNX

新增脚本：

```text
scripts/export_efficientad_raw_onnx.py
```

导出逻辑：

```text
/model/ReduceMax_output_0 → raw_score
/model/Add_output_0       → raw_anomaly_map
```

新 ONNX 输出：

```text
raw_score [1,1]
raw_anomaly_map [1,1,256,256]
```

关键实现注意：

- 使用 `del m.graph.output[:]`，避免 protobuf container 不支持 `.clear()`。
- `make_tensor_value_info` 必须写 shape，不能传 `None`。
- 不使用 `m.graph.node[:] = ...` 这种 RepeatedCompositeContainer 不支持的切片赋值。

结果：

```text
15 类 model_raw.onnx 导出成功
```

## 8. raw ONNX 评估工具

新增脚本：

```text
scripts/evaluate_efficientad_raw_scores.py
```

功能：

- 支持 `--categories`
- 支持 `--csv`
- 计算：
  - raw_score
  - map_max
  - map_mean
  - map_top1
  - map_top01
- 统计 good/defect 分布
- AUROC
- threshold sweep

依赖调整：

```text
原始脚本使用 PIL，但 .venv_rknn 无 Pillow。
已改用 cv2，环境中 cv2 4.11.0 可用。
```

代表类评估：

```text
bottle / metal_nut / pill / screw
共 525 images processed
```

关键结论：

- bottle 的 `raw_score/map_max` 区分度弱，`map_mean` 相对更好。
- 多个类别 raw output 高召回时 FPR 较高。
- T2 不应只作为 hard gate，而应设计成 score provider + optional gate。

## 9. C++ T2 策略更新

新增配置：

```yaml
efficientad_score_mode: map_mean
efficientad_gate_mode: threshold
```

新增 debug 配置：

```yaml
efficientad_gate_mode: pass_all
```

score modes：

```text
raw_score
map_max
map_mean
map_top1
map_top01
```

gate modes：

```text
threshold
pass_all
```

语义：

- `threshold`：正式默认，`final_score > threshold` 才推入 Q2。
- `pass_all`：debug-only，所有帧进入 Q2，但日志显示 `PASS_ALL_WOULD_UPLOAD` 或 `PASS_ALL_WOULD_DROP`。

关键工程判断：

```text
T3 不能补救 T2 漏检，因为 T2 drop 后帧不会进入 Q2。
pass_all 可用于 Prompt 2C 集成调试，但不能作为生产默认，否则 Qwen3-VL 会对所有帧推理导致节拍失控。
```

## 10. raw INT8 RKNN 问题

raw INT8 RKNN 上板后发现：

```text
good-only map_mean ≈ 22~23
defect map_mean ≈ 22~23
raw_score / map_max / topk 大量固定或饱和
```

这与 ONNX raw 分布明显不一致。

结论：

```text
raw INT8 RKNN 输出分布失真，不作为当前 EfficientAD T2 主路线。
```

## 11. FP16/no-quant raw RKNN

修改：

```text
scripts/convert_efficientad_rknn.py
```

新增参数：

```text
--use-raw-onnx
--no-quant
```

行为：

```text
--use-raw-onnx:
  使用 model_raw.onnx
  outputs=["raw_score", "raw_anomaly_map"]

--no-quant:
  rknn.build(do_quantization=False)
  输出 model_raw_noquant.rknn
  不覆盖 model.rknn
```

推荐路线：

```text
model_raw.onnx → model_raw_noquant.rknn → C++ FP16 parse
```

## 12. FP16 输出解析修正

首次 no-quant 上板后发现：

```text
raw_score type=1 size=2
raw_anomaly_map type=1 size=131072
```

这说明每元素 2 bytes，疑似 FP16。旧代码仍按 INT8 解码，导致：

```text
raw_score=-117 / 122
map_max=127
map_top1≈124
map_top01=127
```

修正：

- 根据 `rknn_tensor_attr.type` 区分输出类型。
- INT8/UINT8：`want_float=0` + 手动反量化。
- FP16/FP32：`want_float=1` + 按 float buffer 读取。
- 日志增加：
  - type string
  - parse_mode
  - n_elems
  - size

修复后日志：

```text
output raw_score: type=FP16 parse_mode=fp16_want_float n_elems=1 size=4
output raw_anomaly_map: type=FP16 parse_mode=fp16_want_float n_elems=65536 size=262144
```

## 13. 上板验证结果

### 13.1 bottle

good-only FP16/no-quant 结果恢复正常：

```text
raw_score ≈ 25.75 ~ 52.94
map_mean ≈ 11.47 ~ 12.35
map_top01 ≈ 24.95 ~ 46.65
```

结论：

```text
bottle FP16/no-quant raw RKNN + C++ FP16 parse 通过。
```

### 13.2 representative small set

创建小样本数据：

```text
/tmp/mvtec_representative_small
```

类别：

```text
metal_nut
pill
screw
```

结果：

```text
[T1] scanned 12 images across 3 categories
[T2] model 'metal_nut' loaded
[T2] model 'pill' loaded
[T2] model 'screw' loaded
```

每类均出现：

```text
type=FP16
parse_mode=fp16_want_float
raw_score
raw_anomaly_map
map_mean
final_score
```

无以下错误：

```text
Greater unsupported
rknn_run failed
legacy output
positional fallback
```

结论：

```text
代表类 FP16/no-quant raw RKNN 工程验证通过。
类别切换 reload 逻辑通过。
```

## 14. 已知限制

1. `efficientad_threshold_default: 0.50` 是旧 postprocessor 分数尺度，不适用于 raw output。
2. 每类 raw 分数尺度差异很大，必须做 per-category threshold。
3. 当前 Prompt 2B 目标是工程链路验证，不是最终模型效果评估。
4. `pass_all` 仅用于调试和 Prompt 2C 集成，不代表生产节拍。
5. raw INT8 RKNN 不作为当前主路线。
6. T4 的 `HTTP 0` 是后端不可达，不影响 T2 验证。
7. V4L2 / dma_buf 零拷贝仍保留 TODO，当前主要验证 image_loop。

## 15. 当前冻结点

```text
Phase 7 Prompt 2B:
Representative FP16/no-quant raw EfficientAD RKNN engineering validation passed.
```

下一步：

```text
1. 批量转换 15 类 FP16/no-quant raw RKNN
2. 上传 15 类模型到 Orange Pi 5
3. 运行 15 类 small smoke test
4. Prompt 2B 收尾 commit
5. 新开对话进入 Prompt 2C
```

## 16. 求职/面试可讲点

可以总结为：

> 在 RK3588 部署 EfficientAD-S 时，发现 Anomalib ONNX 的 post_processor 包含 INT8/FLOAT Greater，导致 RKNN Runtime 执行失败。进一步通过 ONNX Runtime 与 graph trace 定位到 pred_score/anomaly_map 已经是 Clip 后处理输出，good/defect 分数饱和。最终通过 ONNX surgery 导出 post_processor 前 raw_score/raw_anomaly_map，并在 C++ T2 中实现 score_mode/gate_mode、FP16 output 解析和 debug pass_all 模式，完成 Orange Pi 5 上 EfficientAD 端侧工程闭环。
