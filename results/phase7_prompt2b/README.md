# Phase 7 Prompt 2B 结果归档

本目录记录 Prompt 2B EfficientAD 边缘集成过程中，WSL 本地与 Orange Pi 板端产生的关键日志。

## WSL 本地需归档文件

如存在：

```text
/tmp/efficientad_raw_eval_representative.csv
/tmp/efficientad_raw_eval_representative.txt
```

复制命令：

```bash
mkdir -p results/phase7_prompt2b

cp /tmp/efficientad_raw_eval_representative.csv results/phase7_prompt2b/ 2>/dev/null || true
cp /tmp/efficientad_raw_eval_representative.txt results/phase7_prompt2b/ 2>/dev/null || true
```

## Orange Pi 板端需归档文件

如存在：

```text
/tmp/phase7_2b_bottle_good_noquant_fixed.log
/tmp/phase7_2b_bottle_all_noquant_fixed.log
/tmp/phase7_2b_representative_small_noquant.log
```

复制命令：

```bash
mkdir -p results/phase7_prompt2b/logs

scp orangepi@192.168.137.66:/tmp/phase7_2b_bottle_good_noquant_fixed.log \
  results/phase7_prompt2b/logs/ 2>/dev/null || true

scp orangepi@192.168.137.66:/tmp/phase7_2b_bottle_all_noquant_fixed.log \
  results/phase7_prompt2b/logs/ 2>/dev/null || true

scp orangepi@192.168.137.66:/tmp/phase7_2b_representative_small_noquant.log \
  results/phase7_prompt2b/logs/ 2>/dev/null || true
```

## 需保留的关键片段

### Greater 报错

```text
ElementwiseLogical: unsupported A type: INT8, B type: FLOAT
Op type: Greater, name: Greater:/post_processor/Greater_1
[T2] rknn_run failed: -1
```

### ONNX raw tensors

```text
raw_score       = /model/ReduceMax_output_0
raw_anomaly_map = /model/Add_output_0
```

### FP16 解析成功日志

```text
output raw_score: type=FP16 parse_mode=fp16_want_float n_elems=1 size=4
output raw_anomaly_map: type=FP16 parse_mode=fp16_want_float n_elems=65536 size=262144
```

### 代表类小样本验证

```text
[T1] scanned 12 images across 3 categories
[T2] model 'metal_nut' loaded
[T2] model 'pill' loaded
[T2] model 'screw' loaded
```

## 说明

- 不要提交大体积 RKNN 模型文件，除非仓库策略明确允许。
- 日志可能较大；如需要，提交 grep 摘要而非完整日志。
- 这些结果支撑 FP16/no-quant raw RKNN 是当前 Prompt 2B 主路线的工程结论。
