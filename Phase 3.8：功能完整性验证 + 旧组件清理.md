完整审计完成。发现了**两套组件系统并存**的问题，以及几个确实丢失的功能点。

---

## 审计结果：新旧组件并存 + 功能丢失清单

### 🔴 最严重问题：两套组件系统共存

项目知识库显示存在两套平行实现：

```
旧系统（Phase 3.2-3.4）：
├── DefectStream.tsx      ← Sheet DetailDrawer + BBox + Trace占位 + 9列表格
├── DashboardStats.tsx    ← 被3.7重写
├── WaterfallChart.tsx    ← 纵向ECharts柱状图（旧版，应已被替代）
├── KpiCards.tsx
├── HeatmapMatrix.tsx
└── AbComparePanel.tsx

新系统（Phase 3.7 V2）：
├── v2/TopBar.tsx
├── v2/BottomStatus.tsx
├── v2/KPIStrip.tsx
├── v2/PipelineWaterfall.tsx   ← 水平SVG甘特图（新版）
├── v2/NPUUtilization.tsx
├── v2/CategorySeverityMatrix.tsx
├── v2/ABCompare.tsx
├── v2/LiveStream.tsx          ← 新的表格组件
├── v2/DetailDrawer.tsx        ← 新的详情抽屉
└── v2/ThroughputChart.tsx
```

**关键问题**：`page.tsx` 到底在用哪套？从截图看 V2 的 TopBar 和瀑布图已经渲染出来了，但旧的 `DefectStream.tsx`（含完整 BBox + Trace 占位 + Sheet Drawer）是否还被引用？如果 V2 `LiveStream.tsx` 替代了 `DefectStream.tsx`，那 Phase 3.4 的所有功能是否都被迁移了？

---

### 🟡 功能丢失 / 可能丢失的清单

| 功能 | Phase 3.2-3.4 旧版 | Phase 3.7 V2 版 | 状态 |
|---|---|---|---|
| BBox CSS 百分比叠加 | ✅ DefectStream.tsx | ❓ v2/DetailDrawer.tsx | **需确认** |
| color-mix() 填充+外发光 | ✅ DefectStream.tsx | ❓ | **需确认** |
| Trace 占位区 (Phase 7) | ✅ DefectStream.tsx | ❓ | **需确认** |
| 断线重连指数退避 | ✅ lib/ws.ts | ✅ 应该未动 | OK |
| typeof window 守卫 | ✅ lib/ws.ts | ✅ 应该未动 | OK |
| Sonner Toast | ✅ DefectStream.tsx | ❓ v2/LiveStream.tsx | **需确认** |
| `API_BASE` 环境变量 | ✅ lib/api.ts | ❓ V2组件是否使用 | **需确认** |
| Variant 紫/青色列 | ✅ 9列表格 | ❓ v2/LiveStream.tsx | **需确认** |
| 旧 WaterfallChart.tsx | 纵向ECharts | 被替代但可能未删 | **需清理** |

---

### 🟢 布局"紧皱干巴"的原因

对比 Image 1（Claude Design）和 Image 2（当前实现），差距主要在：

- **间距不够**：Claude Design 的 Panel 之间有 `gap: 16px`，当前实现可能用了更紧凑的 `gap-4`（16px）但内部 padding 不足
- **字体层级不够分明**：设计稿的 KPI 数字用 `32px+ bold`，子标签用 `10px`，形成强烈对比；当前实现层级扁平
- **瀑布图注释密度**：设计稿每根横条右侧都有毫秒数标注 + 半透明叠层，当前实现标注较少
- **底部状态栏高度**：设计稿约 24px 紧凑单行，当前可能偏高

---

### 给 Claude Code 的补救指令

```
Phase 3.8：功能完整性验证 + 旧组件清理

【1】确认 V2 DetailDrawer 功能完整性
读取 frontend/src/components/v2/DetailDrawer.tsx，逐项检查：
  a. BBox CSS 百分比叠加（left/top/width/height 归一化坐标）
  b. color-mix() 15% 填充 + boxShadow 外发光
  c. bbox 左上角 defect_type 标签
  d. Metadata 2×4 网格（8 字段）
  e. Pipeline Profiler 色条（按比例宽度）
  f. NPU Trace 占位区（trace_events 有/无两种状态）
  g. VLM Raw JSON pre 块

如果缺少任何一项，从旧版 DefectStream.tsx 的 Sheet 部分迁移过来。

【2】确认 V2 LiveStream 功能完整性
读取 frontend/src/components/v2/LiveStream.tsx，检查：
  a. WebSocket 实时追加（使用 lib/ws.ts 的 useDefectWebSocket）
  b. Sonner toast 通知
  c. 表格含 variant 列（紫/青色 badge）
  d. 所有 URL 使用 API_BASE 而非硬编码 localhost
  e. 最大行数限制 .slice(0, 200)

【3】清理旧组件
如果 V2 版本功能完整，删除以下不再使用的旧文件：
  - frontend/src/components/DefectStream.tsx（被 v2/LiveStream + v2/DetailDrawer 替代）
  - frontend/src/components/WaterfallChart.tsx（被 v2/PipelineWaterfall 替代）
  - frontend/src/components/KpiCards.tsx（被 v2/KPIStrip 替代）
  - frontend/src/components/HeatmapMatrix.tsx（被 v2/CategorySeverityMatrix 替代）
  - frontend/src/components/AbComparePanel.tsx（被 v2/ABCompare 替代）

但不要删除 lib/ws.ts 和 lib/api.ts（V2组件仍应使用这两个基础模块）。

【4】确认 page.tsx 只引用 V2 组件，无旧组件残留

【5】npm run build 通过
```

这个补救指令的核心逻辑是：Phase 3.7 做了视觉精修但可能没有迁移 Phase 3.4 的所有功能细节。先检查，缺的补上，确认完整后再清理旧代码。