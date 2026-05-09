Phase 3.7：前端视觉精修 — 对齐 V2 设计稿

目标：当前前端功能正确（WebSocket / DataTable / BBox / ECharts 全部工作），
但视觉效果与 design-reference/ 里的 V2 设计稿差距很大。
需要在保留所有数据逻辑的前提下，重构渲染层使其匹配设计稿。

设计稿位置（按阅读顺序）：
- design-reference/src/v2-primitives.jsx → 颜色系统、字体、基础组件
- design-reference/src/v2-app.jsx        → 整体布局、顶部导航、底部状态栏
- design-reference/src/v2-charts.jsx     → KPI 卡片、瀑布图、NPU 利用率
- design-reference/src/v2-waterfall.jsx  → 水平甘特式瀑布图（非纵向柱状图）
- design-reference/src/v2-stream.jsx     → DataTable 筛选 Tabs、列样式
- design-reference/src/v2-ab.jsx         → AB 5 轴水平条形对比
- design-reference/src/v2-detail.jsx     → DetailDrawer
- design-reference/src/data.jsx          → 模拟数据结构和量级

忽略：tweaks-panel.jsx（Claude Design 调试工具，不需要在前端复现）

工作方式：
1. 先通读所有 design-reference/src/*.jsx 文件，理解 V2 的完整视觉语言
2. 读取 data.jsx，新建 frontend/src/lib/mock-data.ts，
   提供与 data.jsx 同等量级的开发模式模拟数据
3. 让所有组件在 API 不可用时 fallback 到 mock 数据，
   确保 npm run dev 时页面有完整内容可渲染
4. 在后台启动开发服务器（npm run dev &），等待就绪
5. 逐个组件对比现有实现与设计稿的差距，自行决定修改顺序
6. 每完成一个组件后，调用 visual-verify agent 对比效果，
   根据 DIFF REPORT 决定是否需要迭代

约束：
- 数据逻辑不动（fetch / WebSocket / state / types）
- 所有颜色用 globals.css 已定义的 V2 CSS 变量，不新增 hardcode 色值
- design-reference 代码是原生 React + Babel CDN，不能直接复制，
  必须翻译为 Next.js App Router + TypeScript + Tailwind v4
- 后端 API 不改；KPI 卡片若 API 无对应字段，用合理占位值或从现有字段推算
- mock 数据的数值量级应与 data.jsx 一致（不要用 0 或 placeholder）
- 全部完成后执行 npm run build，确认静态导出无报错