# 已有工程证据图清单

> 这些图在当前 Phase 9/10 report-chart 之前生成。作为历史工程证据保留，用于解释架构决策，不作为当前 Phase 10 ORT benchmark 结果。

| Figure ID | 文件 | 来源阶段 | 内容 | 建议用途 | 边界 |
|-----------|------|---------|------|---------|------|
| `fig_existing_efficientad_score_mode_auroc` | `fig_existing_efficientad_score_mode_auroc.png` | Phase 8A | 15 类 5 种 score mode AUROC 热力图 | 说明 EfficientAD 作为 gate 而非 detector | mean AUROC=0.510，非 Phase 10 ORT 指标 |
| `fig_existing_efficientad_threshold_auroc` | `fig_existing_efficientad_threshold_auroc.png` | Phase 8A | per-category 最优阈值 + AUROC 双面板 | 说明单一全局阈值脆弱 | 13/15 类 AUROC < 0.8 |
| `fig_existing_rk3588_qwen3vl_board_perf` | `fig_existing_rk3588_qwen3vl_board_perf.png` | Phase 5/7 | 2B/4B base/LoRA TTFT/decode/RSS/JSON OK 四子图 | 说明 VLM 板端同步调用成本 | 4B JSON OK 仅 65%，非 Phase 10 v1 调用 |
| `fig_existing_pc_vs_rk3588_lora_metrics` | `fig_existing_pc_vs_rk3588_lora_metrics.png` | Phase 5/8B | PC bf16 vs Board W8A8 5 项指标对比 | 说明 W8A8 量化对细粒度字段的坍塌 | defect_type_exact 51.8%→0% |
| `fig_existing_vlm_lora_w8a8_collapse` | `fig_existing_vlm_lora_w8a8_collapse.png` | Phase 5/8B | PC 2B base/LoRA vs Board 2B LoRA 3 项指标 | 说明 LoRA bf16 收益不能迁移到 W8A8 | category_exact 保留，defect_type/bbox 归零 |
| `fig_existing_phase8c_beat_sweep_pressure` | `fig_existing_phase8c_beat_sweep_pressure.png` | Phase 8C | beat_ms vs queue drops + VLM utilization 双面板 | 说明同步 VLM 的背压瓶颈 | pass_all 最坏情况，非 Phase 10 ORT 指标 |

## 使用规则

- 这些图用于解释**为什么**管线演进到 ORT YOLO + 异步 VLM
- 不得用于声称 Phase 10 ORT 的性能指标
- 不得用于声称真实工厂生产数据
- 不得用于声称 VLM 已在 Phase 10 v1 主链路启用
- 图片路径：`docs/figures/report_charts/existing/`

## 引用位置

| 文档 | 引用方式 |
|------|---------|
| `README.md` | `<details>` 折叠，6 张全量 |
| `docs/architecture/MERMAID_ARCHITECTURE_ATLAS.md` | 附录章节，6 张全量 |
| `docs/reports/edge_deployment_summary.md` | §13 工程证据，6 张全量 |
| `docs/reports/PROJECT_REPORT_FOR_PORTFOLIO.md` | §5 工程难点，6 张全量 |
| `_local_archive/interview/INTERVIEW_PREP_EDGE_AI_DEPLOYMENT.md` | §7 视觉证据，按问题组织 |
