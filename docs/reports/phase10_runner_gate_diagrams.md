# Phase 10 Runner Gate Diagrams

> 机制图，使用 Mermaid，不生成 PNG。
> 基于 `docs/experiments/phase10_1b_5d_soak_runner_production_yolo_fix.md`。

## 0. 与报告图表的关系

本文件描述 Phase 10.1b runner 的 safety gates 和 source-of-truth 设计。相关内容已通过以下报告图表在其他文档中可视化：

- **fig03**（ORT snapshot 分布）和 **fig04**（ORT pipeline 延迟）展示 Phase 10 ORT snapshot 和 latency，与 runner 的 source-of-truth 直接相关。
- **fig05**（Phase 9 vs Phase 10 演进）展示系统演进，runner gate diagrams 解释 Phase 10.1b 如何避免 fabricated bbox / confidence / defect_type。
- runner gate diagrams 的 mode state（dry-run → pre-soak → full）和 validation gates A-D 是 Phase 10.1b 的机制设计，不等同于 completed soak。

**边界**：Phase 10.1b pre-soak NOT RUN / READY FOR DRY-RUN。No 200/500 full soak。

---

## 1. Runner Source-of-Truth

```mermaid
flowchart LR
    subgraph SRC["可信源"]
        VAL["val dataset<br/>59 images<br/>metal_nut + cable"]
        YOLO["YOLOv8n-detect<br/>ORT CPU FP32"]
        EAD["EfficientAD-S<br/>FP16 RKNN"]
    end

    subgraph OUT["输出字段"]
        CAT["category<br/>from filename prefix"]
        BBOX["bbox<br/>from YOLO decode"]
        CONF["confidence<br/>from YOLO"]
        DTYPE["defect_type<br/>from YOLO class head"]
        SCORE["anomaly_score<br/>from EfficientAD"]
        LOC["localization_source<br/>= ort_yolov8n_cpu"]
        LBL["label_source<br/>= yolo_class_head"]
    end

    VAL --> CAT
    YOLO --> BBOX & CONF & DTYPE
    EAD --> SCORE
    CAT --> LOC & LBL
```

**边界**：所有字段必须来自模型推理，禁止 `random.uniform()` / `random.choice()` 伪造。

## 2. Mode State Diagram

```mermaid
stateDiagram-v2
    [*] --> DryRun : 初始状态
    DryRun --> PreSoak : dry-run 验证通过
    PreSoak --> Full : pre-soak 验证通过
    Full --> PreSoak : 异常回退

    state DryRun {
        DR1 : 不上报后端
        DR2 : 本地日志验证
        DR3 : 验证 source-of-truth
    }

    state PreSoak {
        PS1 : 小样本上报
        PS2 : 验证端云闭环
        PS3 : 检查 enrichment
    }

    state Full {
        F1 : 长稳上报
        F2 : soak metrics
        F3 : snapshot capture
    }
```

**边界**：当前状态 = pre-soak NOT RUN / READY FOR DRY-RUN。No 200/500 full soak。

## 3. Validation Gates

```mermaid
flowchart LR
    GA["Gate A<br/>Source-of-Truth<br/>所有字段来自模型"] --> GB
    GB["Gate B<br/>Category Boundary<br/>仅 metal_nut + cable"] --> GC
    GC["Gate C<br/>No Fabrication<br/>无 random 伪造"] --> GD
    GD["Gate D<br/>Provenance<br/>localization_source + label_source 非空"]

    PASS["PASS<br/>可进入 dry-run"] --- GD
    FAIL["FAIL<br/>阻塞"] --- GA
```

## 4. Explicit Not Done

| 项目 | 状态 |
|------|------|
| 200/500 full soak | NOT DONE |
| Public snapshot capture | NOT DONE |
| Backend/frontend behavior change | NOT DONE |
| Schema change | NOT DONE |
| Pre-soak run | NOT RUN / READY FOR DRY-RUN |
| Phase 10.1b full soak completed | NOT DONE |

## 5. Curated Val Image Class Pool

```mermaid
flowchart TB
    subgraph MN["metal_nut (29 images)"]
        MN1["bent (8)"]
        MN2["color (7)"]
        MN3["flip (7)"]
        MN4["scratch (7)"]
    end

    subgraph CB["cable (30 images)"]
        CB1["bent_wire (4)"]
        CB2["cable_swap (4)"]
        CB3["combined (4)"]
        CB4["cut_inner_insulation (5)"]
        CB5["cut_outer_insulation (3)"]
        CB6["missing_cable (4)"]
        CB7["missing_wire (3)"]
        CB8["poke_insulation (3)"]
    end

    MN --> POOL["Phase 10 val dataset<br/>59 images total"]
    CB --> POOL
```
