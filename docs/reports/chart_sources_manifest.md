# Chart Sources Manifest

> Updated: 2026-05-28

| Figure ID | Output File | Source Files | Claim Supported | Claim Not Supported | Used In |
|-----------|-------------|-------------|-----------------|---------------------|---------|
| `fig01_phase10_yolo_per_class_map` | `docs/figures/report_charts/fig01_phase10_yolo_per_class_map.png` | `docs/experiments/phase10_training_run_1.md` | Phase 10 YOLOv8n per-class validation | Not real production mAP; curated metal_nut+cable only | README, Atlas, Edge, Portfolio, Interview |
| `fig02_phase10_rknn_smoke_latency` | `docs/figures/report_charts/fig02_phase10_rknn_smoke_latency.png` | `docs/experiments/phase10_training_run_1.md` | RKNN FP16 smoke latency on RK3588 | 2 images only, not full benchmark; RKNN BLOCKED | README, Atlas, Edge, Portfolio, Interview |
| `fig03_phase10_ort_snapshot_distribution` | `docs/figures/report_charts/fig03_phase10_ort_snapshot_distribution.png` | `frontend/public/demo-data/phase10_ort_latest/defects_snapshot.json` | Phase 10 ORT snapshot distribution | ORT CPU fallback; VLM NOT called; only metal_nut+cable | README, Atlas, Edge, Portfolio, Interview |
| `fig04_phase10_ort_pipeline_latency` | `docs/figures/report_charts/fig04_phase10_ort_pipeline_latency.png` | `frontend/public/demo-data/phase10_ort_latest/defects_snapshot.json` | ORT pipeline latency and stage breakdown | ORT CPU fallback, NOT RKNN/NPU; VLM metrics=0 | README, Atlas, Edge, Portfolio, Interview |
| `fig05_phase9_vs_phase10_snapshot_compare` | `docs/figures/report_charts/fig05_phase9_vs_phase10_snapshot_compare.png` | `phase9_soak_archive/manifest.json`, `phase10_ort_latest/manifest.json` | Phase 9 vs 10 system evolution | Not model leaderboard; Phase10 VLM NOT called | README, Atlas, Edge, Portfolio, Interview |
| `fig06_phase8c_beat_sweep_pressure` | `docs/figures/report_charts/fig06_phase8c_beat_sweep_pressure.png` | `results/phase8c_beat_sweep/phase8c_beat_sweep_results.csv` | VLM bottleneck under pressure | pass_all worst-case; not threshold deployment | README, Atlas, Edge, Portfolio, Interview |
| `fig07_efficientad_score_mode_auroc` | `docs/figures/report_charts/fig07_efficientad_score_mode_auroc.png` | `results/phase8_threshold_calibration/score_mode_comparison.csv` | EfficientAD as load-shedding gate | Not a reliable detector; most AUROC < 0.85 | README, Atlas, Edge, Portfolio, Interview |
| `fig08_vlm_quantization_cliff` | `docs/figures/report_charts/fig08_vlm_quantization_cliff.png` | `results/phase8_vlm_ab/board_2b_base_ab_v2_results.csv` + PC baseline | W8A8 quantization cliff for fine-grained fields | Does not claim VLM production deployment | README, Atlas, Edge, Portfolio, Interview |

## Existing Curated Figures

The 6 `fig_existing_*` figures in `docs/figures/report_charts/existing/` are historical engineering evidence from Phase 8/8C/8B. They are used in README `<details>`, Atlas appendix, Edge Summary §13, Portfolio §5.1-5.4, and Interview §7. Source files are in `results/` and `docs/experiments/`.
