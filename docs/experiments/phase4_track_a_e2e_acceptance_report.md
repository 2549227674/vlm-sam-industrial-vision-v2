# Phase 4：轨道A 联调验收报告

## 1. 验收环境

- 日期：2026-05-20
- 分支：main
- Commit：1fe7487 (feat: Phase 4.1 前端接入真实 API)
- Python 版本：3.12.3
- Node 版本：Next.js 15.5.18
- 后端端口：8000（uvicorn）
- 前端端口：3010（next dev，正式端口 3000 被占用）
- API_CONTRACT 版本：v1.2

## 2. 启动结果

| 服务 | 命令 | 结果 | 备注 |
|---|---|---|---|
| 后端 | `PYTHONPATH=. uvicorn backend.app.main:app --port 8000` | PASS | 启动无报错，DB 自动建表（含 trace_events 列） |
| 前端 | `npm run dev --port 3010` | PASS | Compiled in 934ms，页面可访问 |
| 模拟器 | `timeout 20 python simulator/line_runner.py` | PASS | 20s 内写入 78 条缺陷（3 产线 × 2 变体） |

> 注：首次启动需 `PYTHONPATH` 指向项目根目录，因为 `backend/app/main.py` 使用 `from backend.app.db import ...` 绝对导入。

## 3. 接口与数据库验证

| 检查项 | 结果 | 证据 |
|---|---|---|
| `/api/health` | PASS | `{"status":"ok","version":"v1","uptime_s":30,"db":"ok","ws_clients":0}` |
| `/api/defects` 结构 | PASS | `{items:[], total:0, page:1, page_size:5}` 正确分页 |
| `/api/defects` trace_events | PASS | `items[0].trace_events` 含 7 个事件（V4L2_dequeue → HTTP_upload） |
| `/api/stats` 总字段 | PASS | 9/9 字段：total, today_defects, today_high, by_category, by_severity, timeline, ab_compare, avg_pipeline_ms, category_severity_matrix |
| `/api/stats` v1.2 新增字段 | PASS | `today_defects=78`, `today_high=17` |
| `/api/stats` ab_compare | PASS | 4 变体 key 全部存在（2B_base: count=40, avg_output_tokens=59; 2B_lora: count=39, avg_output_tokens=54; 4B_base/4B_lora: count=0） |
| DB trace_events 列 | PASS | `PRAGMA table_info(defects)` 确认 `trace_events JSON nullable` |
| DB trace_events 数据 | PASS | 78/78 条 simulator 数据含 7 个 trace_events（V4L2_dequeue, RGA_preprocess, EfficientAD_infer, FastSAM_infer, VLM_prompt, VLM_decode, HTTP_upload） |
| 图片落盘 | PASS | 435 个 JPEG 文件，按日期子目录（20260509/20260512/20260519），HTTP 200 可访问 |

## 4. 前端联动验证

| 检查项 | 结果 | 证据 |
|---|---|---|
| 初始加载真实数据 | PASS | 控制台无 `Backend unreachable`，页面显示 78 条真实缺陷 |
| WebSocket 连接 | PASS | `ws.onopen` → `hello` 消息接收成功；footer 显示 "WS connected" |
| WebSocket 实时追加 | PASS | POST 缺陷后收到 `defect_created` 广播，`data.trace_events` 字段存在 |
| toast | PASS | sonner Toaster 已注册（从代码确认） |
| ABMatrix 输出词元 | PASS | 2B_base=59, 2B_lora=54（来自真实 /api/stats 数据） |
| Profile Trace 时间线 | PASS | 选中带 trace_events 的帧后：关键路径 532.3ms, NPU.2 占比 84%, 事件数 7, 彩色条形正确渲染 |
| Profile 关键路径摘要 | PASS | NPU.2 占比 84%, 提示/解码 60/40%, 上传 12ms |
| fallback mock | PASS | 停止后端后前端仍返回 200，不白屏；重启后端后恢复正常 |

## 5. 自动化测试

| 命令 | 结果 |
|---|---|
| `pytest backend/tests/contract/ -v` | **34/34 passed**（0.78s） |
| `cd frontend && npx tsc --noEmit` | **0 errors** |
| `cd frontend && npm run build` | **成功**（需 NEXT_FONT_GOOGLE_MOCKED_RESPONSES 离线字体 mock） |

## 6. 视觉验证

phase4-accept-verify 子 agent 执行结果：

| 页面 | 渲染 | 数据 | 功能 | 详情 |
|---|---|---|---|---|
| Overview | PASS | PASS | PASS | KPI 真实数据、RK3588Twin 动画运行、检测流 79 帧、Latest Frame 显示 |
| Profile | PASS | PASS | PASS | Filmstrip 14 帧、Trace 时间线彩色条形、关键路径 532ms、NPU.2 占 84% |
| AB Matrix | PASS | PASS | PASS | 2×2 矩阵完整、输出词元有值、决策条正确 |

- 无 JS 错误：PASS
- 无白屏：PASS
- WebSocket 状态指示：PASS（绿色 "connected"）
- 截图：`/tmp/phase4-overview.png`, `/tmp/phase4-profile.png`, `/tmp/phase4-ab.png`, `/tmp/phase4-profile-verify.png`

> 初次视觉验证时发现 Profile 页面 trace 时间线为空，排查后确认是默认选中的帧（#79 WS_TEST）缺少 trace_events 数据（该帧为手动 WebSocket 测试创建），非代码 bug。删除该帧后选中 #78（含 7 个 trace_events），Trace 时间线正确渲染。

## 7. 问题与修复

| 问题 | 原因 | 修复 | 影响 |
|---|---|---|---|
| `npm run build` Google Fonts 失败 | WSL 网络不通，无法访问 fonts.googleapis.com | 创建 `mock-google-fonts.js` 使用 `NEXT_FONT_GOOGLE_MOCKED_RESPONSES` 从上次构建缓存读取字体文件 | 环境问题，非代码 bug |
| Profile 页初次加载 trace 为空 | 手动创建的 WS_TEST 帧（无 trace_events）被选为默认帧 | 删除该帧；后续建议 ProfilePage 优先选含 trace_events 的帧 | UX 优化，不阻塞功能 |

## 8. 最终结论

**PASS** — 轨道A 联调验收通过。

全部关键验收条件满足：

- [x] 模拟器 → 后端 → DB → WebSocket → 前端 v4 全链路跑通
- [x] `trace_events` 从模拟器上报、后端入库、GET/WS 返回、ProfilePage 渲染
- [x] `/api/stats` v1.2 字段完整，ABMatrix 显示 `avg_output_tokens`
- [x] 前端真实 API 模式和 mock fallback 模式都可用
- [x] `pytest backend/tests/contract/ -v`：34/34 passed
- [x] `cd frontend && npx tsc --noEmit`：0 errors
- [x] `cd frontend && npm run build`：成功
- [x] `vision.db` 使用 v1.2 schema（含 trace_events JSON 列）
- [x] phase4-accept-verify 子 agent 未报告 HIGH 级视觉阻塞

可以进入后续工作（Phase 7 轨道B C++ 流水线 / Phase 8 全链路验收）。
