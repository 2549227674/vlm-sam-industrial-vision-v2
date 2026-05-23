# Phase 9：阈值校准方法学

**日期**：2026-05-24
**关联**：CLAUDE_05 实验验证与 Release Gate

---

## 1. 问题陈述

Phase 8A 使用 MVTec AD **test split** 计算每个类别的 EfficientAD 阈值，随后在**同一 test split** 上评估 AUROC。这是典型的 **calibration-on-test**——阈值在评估数据上拟合，存在方法论缺陷。

### 受影响的指标

| 指标 | 是否受影响 | 方向 |
|---|---|---|
| AUROC | **否** | AUROC 与阈值无关，排序关系保持 |
| good_p95 阈值 | 是 | 拟合到测试分布，可能不泛化 |
| recall@FPR | 是 | 乐观偏差（在校准数据上评估） |
| F1@threshold | 是 | 同上 |
| 生产环境 gate pass rate | 未知 | 取决于真实分布偏移 |

### 不受影响的指标

- AUROC 在 score mode 之间的比较（raw_score vs map_mean 等）——同一 split 上的相对排序有效
- ONNX vs RKNN AUROC delta——同一 split 上的相对比较有效
- "T2 是 load shedding gate，不是检测器"的结论——基于 AUROC < 0.80（14/15 类），与阈值无关

## 2. 当前校准方法（Phase 8A-Fix-Fix）

```text
数据集：MVTec AD test split，15 类，共 1725 张图
每类 good 样本数：12（toothbrush）~ 116（cable）

阈值公式：good_p95（good 图片 raw_score 的 95 分位数）
Score mode：raw_score（EfficientAD raw 输出的 ReduceMax）

结果：edge/config.yaml 中的 per_category_threshold
```

### 为什么选 good_p95

- 设定 gate 约放行 5% 的 good 图片（假阳性进入 VLM）
- 保守策略：大部分 good 图片被过滤，减少 VLM 负载
- 不优化缺陷召回率——低于阈值的缺陷被静默丢弃

### 局限性

1. **小样本问题**：toothbrush 仅 12 张 good 图片，p95 的置信区间很宽
2. **无 held-out 评估**：阈值和评估指标使用同一数据
3. **仅 MVTec**：无生产环境数据验证
4. **分布偏移**：真实缺陷分数可能与 MVTec test split 不同

## 3. 推荐的正确方法

### 方案 A：校准/测试分离（首选）

```text
每个类别：
  1. good 图片拆分：50% 校准集，50% 测试集
  2. defect 图片拆分：50% 校准集，50% 测试集
  3. 在校准集 good 图片上计算阈值（good_p95）
  4. 在测试集上评估：recall、FPR、F1

挑战：小样本类别（toothbrush：12 good + 30 defect）
  → 6 张 good 用于校准，6 张用于测试
  → 6 个样本的 p95 不可靠
```

### 方案 B：Bootstrap 置信区间

```text
每个类别：
  1. 对 good 图片做 1000 次 bootstrap 重采样
  2. 每次计算 good_p95
  3. 报告阈值的中位数和 95% CI
  4. 报告 defect 图片在阈值处的 recall CI

优点：适用于小样本
缺点：仍是 calibration-on-test（无 held-out 数据）
```

### 方案 C：留一交叉验证

```text
每个类别：
  1. 对每张 good 图片，在剩余 good 图片上计算 p95
  2. 评估：被留出的图片是否低于阈值？
  3. 期望假阳性率：~5%

优点：所有数据同时用于校准和评估
缺点：计算量大；仍在同一分布内
```

## 4. 实际影响评估

### T2 Gate 是负载卸载，不是检测器

Phase 8 的核心发现是 T2 EfficientAD gate 是**负载卸载控制器**：

- 目的：通过过滤明显 good 的图片来减少 VLM 工作量
- **不是**缺陷检测器：AUROC < 0.80（14/15 类）意味着区分能力差
- 阈值校准控制 VLM 负载与遗漏缺陷之间的权衡

### calibration-on-test 对部署的影响

| 场景 | 影响 |
|---|---|
| 生产环境 gate pass rate 略高 | 可能——阈值可能偏紧 |
| 生产环境 gate pass rate 略低 | 可能——阈值可能偏松 |
| VLM 过载 | 不太可能——threshold 模式已过滤约 95% good 图片 |
| 遗漏缺陷 | 预期行为——部分缺陷低于阈值被丢弃 |

### 缓解措施

1. **阈值模式设计保守**：good_p95 意味着约 5% 的 good 图片假阳性率。即使真实率为 7-10%，VLM 负载增幅有限。
2. **VLM 是最终裁判**：即使缺陷通过 gate，VLM 做最终分类。缺陷在 T2 被拦截意味着永远不进入 VLM——这是真正的风险。
3. **Soak test 验证稳定性**：Phase 9 threshold soak test 验证流水线在 threshold 模式下稳定运行 30 分钟以上。这是系统级验证，不是校准验证。

## 5. 可以声称 vs 不能声称

### 可以声称

- T2 gate 通过 good_p95 阈值过滤约 95% 的 good 图片，减少 VLM 负载
- Threshold 模式在长时间运行条件下稳定（soak test 验证）
- Per-category 阈值是工程起始值，非生产认证值
- AUROC 在 score mode 之间的比较有效（相对排序保持）
- 系统在 threshold 模式下端到端工作正常

### 不能声称

- 阈值已通过生产认证
- 阈值处的 recall 精确为 X%（calibration-on-test 偏差）
- 阈值可泛化到非 MVTec 数据
- good_p95 是最优阈值策略

## 6. 后续工作建议

生产部署前：

1. **收集生产数据**：即使每类 50-100 张来自目标域的图片
2. **分离校准/测试**：用 MVTec train split 校准，test split 评估
3. **Bootstrap CI**：对小样本报置信区间
4. **监控 gate pass rate**：生产环境跟踪实际 pass rate vs 预期 5%
5. **调整阈值**：基于生产数据，而非仅 MVTec

对于当前项目（课程设计/求职作品集）：

- 记录 calibration-on-test 局限性（本文档）
- 使用 soak test 作为系统级验证
- 报告 AUROC 时注明其与阈值无关
- 报告 gate pass rate 时注明数据来自校准集
