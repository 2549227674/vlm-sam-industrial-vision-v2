# Phase 7 Prompt 2C 交接文档

## 当前冻结点

Phase 7 Prompt 2B 已完成代表类 EfficientAD FP16/no-quant raw RKNN 验证。

当前冻结状态：

```text
Prompt 2B：代表类验证通过。
下一步：批量 15 类 FP16/no-quant raw RKNN 转换上传 + 15 类 smoke test。
然后开始 Prompt 2C：FastSAM + Qwen3-VL。
```

## 已完成

### Prompt 1

- CMake 基础设施
- Config loader
- Http client
- RKNN/RKLLM/RGA 真实库发现
- 板上 build 通过

### Prompt 2A

- T1 image_loop
- MockPipelineWorker
- T4 UploadWorker
- 主线程四线程串联
- Mock meta JSON 生成

### Prompt 2B

- 真实 EfficientAD T2 Worker
- 按类别模型加载
- raw ONNX 导出
- raw RKNN 转换支持
- FP16/no-quant 路线
- 输出类型感知解析
- score_mode
- gate_mode
- pass_all debug 配置
- threshold 正式配置
- 代表类验证通过：
  - bottle
  - metal_nut
  - pill
  - screw

## 当前 EfficientAD 路线

使用：

```text
model_raw.onnx
→ model_raw_noquant.rknn
→ C++ raw_score/raw_anomaly_map
→ score_mode=map_mean
→ gate_mode=threshold（正式）
→ gate_mode=pass_all（仅调试）
```

不使用原始 post_processor 输出作为 T2 gate：

```text
pred_score
anomaly_map
pred_label
pred_mask
```

不使用 raw INT8 RKNN 作为当前主路线，因为板端测试显示分布失真。

## 关键配置

正式：

```yaml
efficientad_score_mode: map_mean
efficientad_gate_mode: threshold
```

调试：

```yaml
efficientad_score_mode: map_mean
efficientad_gate_mode: pass_all
```

`pass_all` 仅调试用。

## 阈值说明

`efficientad_threshold_default: 0.50` 是旧 post_processor 尺度的占位值。raw output 分数分布不同，per-category raw threshold 必须在 Phase 8 校准后才能用于正式评估。

## Prompt 2C 前置任务

先完成：

```bash
source .venv_rknn/bin/activate
python scripts/convert_efficientad_rknn.py \
  --use-raw-onnx \
  --no-quant \
  --skip-accuracy-analysis
```

然后用 staging + tar pipe 上传全部 15 类。

推荐上传方式：

```bash
cd ~/vlm-sam-industrial-vision-v2

CATS="bottle cable capsule carpet grid hazelnut leather metal_nut pill screw tile toothbrush transistor wood zipper"

STAGE=/tmp/ead_fp16_upload
rm -rf "$STAGE"
mkdir -p "$STAGE"

for c in $CATS; do
  src="models/efficientad_models/$c/model_raw_noquant.rknn"
  if [ ! -f "$src" ]; then
    echo "MISSING: $src"
    exit 1
  fi
  mkdir -p "$STAGE/$c"
  cp "$src" "$STAGE/$c/model.rknn"
done

tar -C "$STAGE" -cf - . | ssh orangepi@192.168.137.66 '
set -e
DST=/home/orangepi/models/efficientad_models

for c in bottle cable capsule carpet grid hazelnut leather metal_nut pill screw tile toothbrush transistor wood zipper; do
  mkdir -p "$DST/$c"
  if [ -f "$DST/$c/model.rknn" ]; then
    cp "$DST/$c/model.rknn" "$DST/$c/model_before_fp16_raw_backup.rknn"
  fi
done

tar -C "$DST" -xf -

echo "uploaded fp16/no-quant raw RKNN models:"
for c in bottle cable capsule carpet grid hazelnut leather metal_nut pill screw tile toothbrush transistor wood zipper; do
  ls -lh "$DST/$c/model.rknn"
done
'
```

## 15 类 smoke test 建议

在 Orange Pi 上创建小样本 15 类数据：

```text
/tmp/mvtec_15cls_small
```

每类：
- 1~2 张 good 图
- 1~2 张 defect 图（如有）

使用 `edge/config.debug.yaml` 派生配置，`gate_mode=pass_all`。

smoke test 必须验证：

```text
model '{category}' loaded
type=FP16
parse_mode=fp16_want_float
raw_score
raw_anomaly_map
map_mean
final_score
decision
```

不应出现：

```text
Greater unsupported
rknn_run failed
legacy output
positional fallback
```

## Prompt 2C 范围

15 类 smoke 通过后，实现 T3：

- FastSAM RKNN 推理
- FastSAM 输出解析
- bbox 提取
- bbox 净化
- Qwen3-VL RKLLM JSON 生成
- 保持 T1/T2/T3/T4 四线程结构
- 保持 T4 API 契约不变
- 不引入 Python 服务
- `pass_all` 仅用于调试集成
