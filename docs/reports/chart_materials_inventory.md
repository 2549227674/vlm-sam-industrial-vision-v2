# 图表素材清单

> 扫描日期：2026-05-28
> 仅列出可从仓库已有文件解析的数据源。不包含 models/、datasets/、backend/static/defects/ 大资产。

## 高置信度（结构化 CSV/JSON）

| Phase | Source File | Data Type | Chart Candidate | Confidence | Doc Integration |
|-------|-----------|-----------|-----------------|------------|----------------|
| 8C | `results/phase8c_beat_sweep/phase8c_beat_sweep_results.csv` | CSV | beat_ms vs queue_drop / VLM utilization / RSS / decode_tps | high | README, Atlas, Edge, Portfolio, Interview |
| 8A | `results/phase8_threshold_calibration/score_mode_comparison.csv` | CSV | 15 类 × 5 score_mode AUROC 热力图 | high | README, Atlas, Edge, Portfolio, Interview |
| 8A | `results/phase8_threshold_calibration/threshold_summary.csv` | CSV | per-category threshold + AUROC | high | — |
| 8B | `results/phase8_vlm_ab/board_2b_base_ab_v2_results.csv` | CSV | 2B base per-sample VLM metrics | high | README, Atlas, Edge, Portfolio, Interview |
| 8B | `results/phase8_vlm_ab/board_2b_lora_controlled_rerun_results.csv` | CSV | 2B LoRA per-sample VLM metrics | high | — |
| 10 | `frontend/public/demo-data/phase10_ort_latest/manifest.json` | JSON | ORT snapshot metadata | high | README, Atlas, Edge, Portfolio, Interview |
| 10 | `frontend/public/demo-data/phase10_ort_latest/defects_snapshot.json` | JSON | 40 records: category/defect_type/severity/confidence/pipeline_ms/trace_events | high | README, Atlas, Edge, Portfolio, Interview |
| 9 | `frontend/public/demo-data/phase9_soak_archive/manifest.json` | JSON | Phase9 soak metadata | high | README, Atlas, Edge, Portfolio, Interview |
| 9 | `results/phase9_public_demo_seed/manifest.json` | JSON | Phase9 public demo seed metadata | high | — |

## 中置信度（Markdown 表格可解析）

| Phase | Source File | Data Type | Chart Candidate | Confidence |
|-------|-----------|-----------|-----------------|------------|
| 10 | `docs/experiments/phase10_training_run_1.md` | MD table | YOLOv8n per-class mAP / precision / recall | medium |
| 10 | `docs/experiments/phase10_training_run_1.md` | MD table | RKNN FP16 smoke latency stack | medium |
| 8B | `results/phase8_vlm_ab/board_2b_base_vs_lora_ab_v2.md` | MD table | 2B base vs LoRA VLM metrics comparison | medium |
| 8B | `results/phase8_vlm_ab/board_2b_base_ab_v2_summary.md` | MD table | 2B base VLM performance summary | medium |
| 8B | `results/phase8_vlm_ab/lora_conversion_audit.md` | MD | LoRA conversion audit | medium |

## 低置信度（叙述/机制图材料）

| Phase | Source File | Data Type | Chart Candidate | Confidence |
|-------|-----------|-----------|-----------------|------------|
| 10.1b | `docs/experiments/phase10_1b_5d_soak_runner_production_yolo_fix.md` | MD | Runner safety gates / source-of-truth / mode state | low |
| 10.1b | `docs/experiments/phase10_1b_live_stream_soak_plan.md` | MD | Pre-soak readiness / stop conditions | low |
| 9 | `docs/experiments/phase9_experiment_validation_release_gates.md` | MD | Release gate status board | low |
| 9 | `docs/experiments/phase9_public_demo_post_deploy_hardening.md` | MD | Phase9 hardening steps | low |

## 边界说明

| 数据 | 边界 |
|------|------|
| Phase 10 YOLO mAP | metal_nut + cable 12 类 185 images，非全量 MVTec |
| Phase 10 RKNN smoke | 2 张图测试，非 full deployment benchmark |
| Phase 10 ORT snapshot | ORT CPU fallback，非 RKNN/NPU；VLM NOT called |
| Phase 9 soak archive | 20 unique records（API pagination limit），full run 366+ frames |
| Phase 8C beat sweep | pass_all worst-case，非 threshold deployment traffic |
| Phase 10.1b | No 200/500 full soak；pre-soak NOT RUN / READY FOR DRY-RUN |
