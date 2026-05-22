# RK3588 边缘 AI 工业视觉检测系统：工程部署总结

> **项目**：vlm-sam-industrial-vision-v2
> **硬件**：Orange Pi 5 Plus（RK3588，16GB RAM）
> **定位**：三阶段工业视觉缺陷检测流水线的完整端侧部署与性能评估
> **作者**：[待填写]
> **状态**：Phase 8D 草稿（待完善）

---

## 摘要（Executive Summary）

本项目在 RK3588 SoC 上实现了 EfficientAD-S → FastSAM → Qwen3-VL 的三阶段工业缺陷检测流水线，完成端云分离架构部署，并通过系统性实验定量分析了 EfficientAD raw score 的判别能力、VLM 变体的质量-延迟权衡、以及 W8A8 量化对 LoRA 微调增益的影响。

**核心指标（2B base W8A8，threshold 模式）**：
- True E2E：upload_ok=24/24，json_parse_ok=100%（有效帧），RSS≈3298MB
- EfficientAD 推理：~300ms/帧
- FastSAM 推理：~170ms/帧
- Qwen3-VL 推理：mean 10.7s/帧，decode 9.7 tok/s
- 最小稳定 beat：10000ms（pass_all）；threshold 模式 5000ms 可行

---

## 1. 项目目标与架构

### 1.1 目标
[TODO: 1-2 段，说明工业检测场景、边缘部署动机]

### 1.2 端云分离架构
[TODO: 引用 ARCHITECTURE.md，说明 edge C++ pipeline + cloud FastAPI/Next.js 的分工]

### 1.3 四线程 C++ 流水线

```
T1 image_loop → Q1 → T2 EfficientAD-S → Q2 → T3 FastSAM+Qwen3-VL → Q3 → T4 Upload
```

[TODO: 每个线程一句话说明职责，引用关键数据]

---

## 2. 模型部署与工程排障

### 2.1 EfficientAD-S：RKNN FP16 Raw 部署

**挑战**：
- post-processor（Clip+Normalize+Sigmoid）因 `Greater` 节点类型不兼容无法在 RKNN 上运行
- INT8 量化导致 anomaly map 分布失真

**解决**：
- 导出 raw ONNX，截断 post-processor
- 使用 FP16/no-quant RKNN（精度等价 ONNX，max AUROC delta = 0.024）
- 确定最优 score mode：raw_score（mean AUROC 0.5320 vs map_mean 0.4561）

**T2 gate 定位**：
15 类全部 AUROC < 0.80（best: tile 0.8193），T2 是负载脱落门控，非精确分类器。good_p95 阈值控制 ~5% false positive rate，保证 T3 不过载。

### 2.2 FastSAM：FP16 RKNN 部署

[TODO: 简述 INT8 精度回退问题 → FP16 解决]

### 2.3 Qwen3-VL RKLLM 部署

**主要排障（共 4 个）**：
1. RKLLM runtime 版本不匹配（v1.2.1 vs v1.2.3）→ 替换系统库
2. n_image_tokens 计算错误（784 vs 196）→ 修正为 patch_h × patch_w
3. max_new_tokens 导致 JSON 截断 → 增加 tokens + compact prompt（196→89 tokens）
4. JSON 提取 depth-matching 失败 → 改为 rfind('}') 容忍截断

[引用 docs/ENGINEERING_FINDINGS.md F-VLM-01 到 F-VLM-03]

---

## 3. Phase 8 量化评估

### 3.1 EfficientAD score mode 对比

[TODO: 插入 5 种 mode AUROC 表格]

### 3.2 VLM 变体 A/B 评估

**板端性能对比**：

| 指标 | 2B base | 4B base | 2B LoRA（参考）|
|---|---|---|---|
| TTFT | 1900ms | 4650ms | 1914ms |
| decode_tps | 9.7 | 4.9 | 9.9 |
| RSS | 3285MB | 5689MB | 3274MB |
| qwen3vl_ms | 10548ms | 19500ms | ~26000ms* |
| json_parse_ok | 100% | 100%（非 carpet）| 100% |
| defect_type_exact | 0% | 0% | 0% |

*含 499 token 退化帧

**PC 质量对比**（GPU bf16，409 样本）：

| 指标 | 2B base | 2B LoRA |
|---|---|---|
| defect_type_exact | 11.5% | **51.8%** |
| category_exact | 53.8% | **95.1%** |
| bbox_iou>=0.5 | 1.2% | **47.7%** |

### 3.3 W8A8 量化对 LoRA 增益的影响

**核心发现**：

```
PC LoRA bf16：defect_type_exact = 51.8%
Board LoRA W8A8：defect_type_exact = 0%

category_exact：95.1% → 93%（基本保留）
defect_type_exact：51.8% → 0%（完全归零）
```

**机制**：LoRA rank-32 delta 权重幅值 << base 权重，W8A8 量化分辨率（max(|W|)/127）不足以保留 delta，细粒度分类知识丢失，粗粒度 category 知识因编码冗余而保留。

验证：LoRA 已正确 merge-then-convert（bash_history + key check + SHA256 跨平台一致）。问题是硬件约束（RK3588 LLM 路径 W8A8 only），不是实现错误。

### 3.4 系统压力测试（beat_ms sweep）

[TODO: 插入 Phase 8C 结果表格 + VLM/beat ratio 公式]

---

## 4. 已知限制

1. **EfficientAD 判别能力有限**：raw output AUROC < 0.80，T2 gate 只能做负载脱落
2. **W8A8 破坏 LoRA 增益**：RK3588 硬件限制，无法使用高精度量化
3. **4B carpet 静默失败**：spatial patch merge 排列错误，修复路径已明确
4. **FastSAM 只输出 bbox**：mask decode 未实现
5. **Vision embedding 未缓存**：相同图片每次重新推理

---

## 5. 下一步优化

1. 实现 C++ post-processor（绕过 RKNN Greater 节点），恢复 EfficientAD 精度
2. 修复 4B vision encoder spatial permutation（支持所有类别）
3. 实现 FastSAM mask decode（输出像素级分割）
4. 探索 vision embedding cache（相同图片跳过 vision encoder）
5. 评估 enable_thinking 模式对输出质量的影响

---

## 附录

### A. 环境配置
[TODO: 硬件、软件版本、模型文件清单]

### B. 实验数据索引
[TODO: 指向 results/ 各子目录]

### C. 关键工程发现索引
见 docs/ENGINEERING_FINDINGS.md
