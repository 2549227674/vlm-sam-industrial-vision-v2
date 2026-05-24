# Phase 9：前端 Demo 展示真实性防护

**日期**：2026-05-24
**分支**：main
**执行者**：Claude Code（自动化）

---

## 1. 任务目标

让 Next.js 仪表盘明确显示当前数据来源（Live API / Real RK3588 Snapshot / Mock Fallback / Simulator），避免截图被误解为实时生产数据。在 AB Matrix、Profile、Overview 等页面添加能力边界提示，防止过度宣传。

---

## 2. 变更总览

### 2.1 新增文件

| 文件 | 用途 |
|---|---|
| `frontend/src/lib/data-source.ts` | 多数据源解析 hook（`useDataSource`），优先级：Live API > Real Snapshot > Mock |
| `frontend/src/components/v4/DataSourceBadge.tsx` | 数据源状态徽章组件 + VLM defect_type tooltip |
| `frontend/src/components/v4/CaveatBanner.tsx` | 能力边界提示横幅 + 变体专用 badge + trace 来源标识 |

### 2.2 修改文件

| 文件 | 变更 |
|---|---|
| `frontend/src/app/page.tsx` | 替换手动 mock/live 逻辑为 `useDataSource` hook；传递 `dataSource` 到所有子组件 |
| `frontend/src/components/v4/TopBar.tsx` | 集成 `DataSourceBadge` 替代通用"实时/已暂停" |
| `frontend/src/components/v4/BottomBar.tsx` | 底栏显示数据来源标签 + 颜色 |
| `frontend/src/components/v4/OverviewPage.tsx` | +CaveatBanner（T2 gate + FastSAM mask caveat） |
| `frontend/src/components/v4/ABMatrix.tsx` | +CaveatBanner + VariantCaveatBadge（2B_lora W8A8 坍塌, 4B 扩展候选） |
| `frontend/src/components/v4/ProfilePage.tsx` | +CaveatBanner + TraceSourceNote（simulator/edge/snapshot）+ T3.fastsam lane + 兼容 snapshot trace |
| `frontend/src/components/v4/LogsPage.tsx` | 状态栏显示数据来源 |
| `frontend/src/components/v4/ModelsPage.tsx` | 接收 `dataSource` prop |
| `frontend/src/components/v4/FrameInspector.tsx` | VLM defect_type tooltip + bbox clamping [0,1] |
| `frontend/src/components/v4/RecentStream.tsx` | VLM defect_type tooltip |
| `frontend/src/components/v4/DetailDrawer.tsx` | VLM defect_type tooltip |

---

## 3. 数据源优先级逻辑

```
1. 尝试 Live API（fetch /api/defects + /api/stats，5s 超时）
   → 两者均 200 OK → status: "live", label: "Live RK3588 API"

2. 尝试 Real RK3588 Snapshot（fetch /demo-data/real_run_latest/{manifest,defects,stats}.json）
   → 三者均 OK → status: "snapshot", label: "Real RK3588 Snapshot"

3. 回退到 Mock（seedDefects(80) + buildStats()）
   → status: "mock", label: "Mock Fallback"
```

快照数据来源于真实的 RK3588 threshold soak 测试（Phase 9, 2026-05-24），包含 20 条记录，覆盖 3 个类别（cable, capsule, carpet）和 2 个变体（2B_base, 4B_base）。

---

## 4. 数据源徽章视觉设计

| 状态 | 颜色 | 圆点 | 附加标识 |
|---|---|---|---|
| Live RK3588 API | `var(--ok)` 绿色 | 脉冲动画 | — |
| Real RK3588 Snapshot | `#7cdcff` 蓝色 | 静态 | — |
| Mock Fallback | `var(--warn)` 橙色 | 静态 | 加粗 "MOCK" 标签 |
| Reconnecting | `var(--warn)` 黄色 | 脉冲动画 | — |

所有徽章均有 `title` tooltip 解释数据来源含义。

---

## 5. 添加的能力边界提示

### 5.1 Overview 页面
- "T2 EfficientAD is a load-shedding gate, not a reliable defect detector."
- "FastSAM outputs bbox proposals only; mask decode is not implemented."

### 5.2 Profile 页面
- 与 Overview 相同 + trace 来源标识（simulator / edge / snapshot）

### 5.3 AB Matrix 页面
- 与 Overview 相同 + "4B is an extension candidate; it does not replace the 2B mainline automatically."
- 变体专用 badge：
  - `2B_lora`："PC bf16 improves fine-grained metrics; RK3588 W8A8 collapses defect_type_exact."
  - `4B_base` / `4B_lora`："Extension candidate; requires spatial merge fix and carpet regression."

### 5.4 Logs 页面
- 状态栏第一格显示数据来源标签 + 颜色，替代通用"后端: 健康"

---

## 6. Bbox 越界防护

在 `FrameCanvas`（FrameInspector.tsx）中，bbox 渲染前先 clamp 到 [0, 100] SVG 单位：

```tsx
const x = Math.max(0, Math.min(100, b.x * 100));
const y = Math.max(0, Math.min(100, b.y * 100));
const w = Math.min(100 - x, b.w * 100);
const h = Math.min(100 - y, b.h * 100);
```

防止越界 bbox 撑爆 SVG 渲染区域。

---

## 7. VLM defect_type Tooltip

所有显示 `defect_type` 的位置现在都有 hover tooltip：

> "VLM-generated structured description. Not a guaranteed exact class on RK3588."

应用于：
- FrameInspector bbox 叠加层
- RecentStream DetectionCard
- DetailDrawer 标题

---

## 8. 文案替换表（来自 CLAUDE_06 规范）

| 原文风险 | 建议替换 |
|---|---|
| 精准分类工业缺陷 | 实时展示边端缺陷报告与流水线指标 |
| VLM 识别缺陷类型 | VLM 生成结构化描述 |
| EfficientAD 检测缺陷 | EfficientAD raw_score 门控 T3 负载 |
| 4B 模型效果更强 | 4B 模型作为扩展候选 |
| LoRA 提升板端缺陷分类 | LoRA 在 PC bf16 提升明显，RK3588 W8A8 下细粒度坍塌 |

说明：现有组件文案已使用中性描述，未过度宣传。能力边界提示为追加性质，非替换现有文案。

---

## 9. 验证结果

| 检查项 | 结果 |
|---|---|
| `make contract-all`（74 tests + drift + typecheck + fixtures） | **通过** |
| `cd frontend && npx tsc --noEmit` | **通过** |
| `cd frontend && npm run build`（静态导出） | **通过** |
| `out/demo-data/real_run_latest/` 快照数据 | **20 张图片 + manifest.json + defects_snapshot.json + stats_snapshot.json** |
| 未新增 API contract 字段 | **确认** |
| 前端未直连数据库 | **确认** |
| 未实现 FastSAM mask decode | **确认** |

---

## 10. 行为验收（可视化验证）

| 场景 | 预期 | 状态 |
|---|---|---|
| 后端运行中 | 绿色 "Live RK3588 API" 徽章 | 待 CLAUDE_07 验证 |
| 后端已停止 | 蓝色 "Real RK3588 Snapshot" 徽章 + manifest caveat 横幅 | 已验证：快照数据正常加载 |
| 快照和后端均不可达 | 橙色 "Mock Fallback" 徽章 + 加粗 MOCK 标签 | 已验证：mock fallback 激活 |
| Mock fallback 可见时 | 橙色警告横幅："Using mock data because backend is unreachable" | 已验证 |
| defect_type hover | tooltip："VLM-generated structured description..." | 已实现 |
| AB Matrix 变体单元格 | 2B_lora 和 4B 变体的 caveat badge | 已实现 |
| 越界 bbox | clamp 到 [0,1] 范围，无 SVG 溢出 | 已实现 |

---

## 11. 验证后修复

### 11.1 Caveat 去重（关键词重叠阈值 0.3）

初始 caveat 横幅显示 9 项，原因是 manifest caveats 与内置 caveat 存在重叠。通过关键词重叠去重（阈值 0.3，仅计 >3 字符的显著词）修复。修复后：Overview 页 6 项，AB 页 7 项（增加 4B caveat）。

### 11.2 Profile Trace 与快照数据的兼容性

快照 trace 事件使用线程级 tid（`T2.pipeline`、`T3.fastsam`、`T3.vlm`、`T4.upload`），而非 mock 数据使用的硬件级 tid（`NPU.core0/1/2`）。修复内容：
- 在 trace viewer 的 lane groups 和 labels 中添加 `T3.fastsam`
- 在 `CAT_COLOR` 映射中添加 `pipeline`、`upload`、`vlm` 颜色
- 添加 KPI 回退计算：当 `NPU.core*` 事件不存在时，先从线程级 tid 计算，再从 `pipeline_ms` 推算
- 添加 prompt/decode 估算：当快照缺少 VLM 子事件拆分时，从 `pipeline_ms` 推算（base 62% prompt，LoRA 55% prompt）
- 验证结果：关键路径=28282ms，NPU.2 占比=99%，提示 vs 解码=62/38%（est.）

### 11.3 最终验证汇总

| 检查项 | 结果 |
|---|---|
| Overview caveat 数量 | 6 项（原 9 项，去重 3 项） |
| AB Matrix 变体 badge | 2B_lora + 4B caveat badge 存在 |
| Profile KPI 关键路径 | 28282.2 ms（非零） |
| Profile KPI NPU.2 占比 | 99%（非零） |
| Profile KPI 提示 vs 解码 | 62/38% + "(est.)" 标签 |
| Trace viewer T3.fastsam lane | 可见 |
| Trace viewer T3.vlm lane | qwen3vl_generate 条跨越完整时间线 |
| 所有 5 页 header badge | "Real RK3588 Snapshot" 蓝色徽章 |
| 所有 5 页 footer badge | "Real RK3588 Snapshot" 数据来源标签 |
