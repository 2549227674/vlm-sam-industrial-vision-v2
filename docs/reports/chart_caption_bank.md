# Chart Caption Bank

> Updated: 2026-05-28

## fig01_phase10_yolo_per_class_map

**Caption**: Phase 10 YOLOv8n per-class validation: metal_nut + cable (12 classes, 185 images). Best mAP50=0.593. Weak classes: cut_outer_insulation (0.239), poke_insulation (0.287), combined (0.338). Strong: flip (0.995), missing_cable (0.995).
**Use in README**: Yes — Phase 9/10+ 定量工程证据图 section
**Use in Portfolio**: Yes — §5.5 Phase 9/10+ 定量证据图
**Use in Edge Summary**: Yes — §13B.1
**Use in Interview**: Yes — Q1 (localizer 验证)
**Boundary**: Curated 12-class subset, not full MVTec 15-class. Not real production mAP.

## fig02_phase10_rknn_smoke_latency

**Caption**: RK3588 RKNN FP16 smoke latency: preprocess 37.8ms + inference 95.2ms + postprocess 3.7ms = 136.7ms total.
**Use in README**: Yes — Phase 9/10+ 定量工程证据图 section
**Use in Portfolio**: Yes — §5.5A
**Use in Edge Summary**: Yes — §13B.1
**Use in Interview**: Yes — Q1
**Boundary**: 2-image smoke test, not full deployment benchmark. RKNN numeric consistency BLOCKED.

## fig03_phase10_ort_snapshot_distribution

**Caption**: Phase 10 ORT snapshot: 40 records, cable + metal_nut categories, ORT CPU fallback.
**Use in README**: Yes — Phase 9/10+ 定量工程证据图 section
**Use in Portfolio**: Yes — §5.5A
**Use in Edge Summary**: Yes — §13B.2
**Use in Interview**: Yes — Q1
**Boundary**: ORT CPU fallback, NOT RKNN/NPU. VLM NOT called. Only metal_nut + cable.

## fig04_phase10_ort_pipeline_latency

**Caption**: Phase 10 ORT pipeline latency: EfficientAD ~350ms, YOLOv8n ORT ~188ms.
**Use in README**: Yes — Phase 9/10+ 定量工程证据图 section
**Use in Portfolio**: Yes — §5.5A
**Use in Edge Summary**: Yes — §13B.2
**Use in Interview**: Yes — Q1
**Boundary**: ORT CPU fallback. VLM metrics = 0 (not called). upload=0.0 due to sequencing constraint.

## fig05_phase9_vs_phase10_snapshot_compare

**Caption**: Phase 9 (VLM pipeline, 30.2min soak) vs Phase 10 (ORT CPU, 27min soak) system evolution.
**Use in README**: Yes — Phase 9/10+ 定量工程证据图 section
**Use in Portfolio**: Yes — §5.5B
**Use in Edge Summary**: Yes — §13B.3
**Use in Interview**: Yes — Q2 (双主线)
**Boundary**: Comparison is system evolution, not model leaderboard. Phase 10 VLM NOT called.

## fig06_phase8c_beat_sweep_pressure

**Caption**: Phase 8C beat sweep: VLM utilization crosses 1.0 bottleneck at ~10000ms. At 5000ms, 23 queue drops accumulate.
**Use in README**: Yes — Phase 9/10+ 定量工程证据图 section
**Use in Portfolio**: Yes — §5.5C
**Use in Edge Summary**: Yes — §13B.4
**Use in Interview**: Yes — Q3 (VLM 瓶颈)
**Boundary**: pass_all worst-case. Not threshold deployment traffic.

## fig07_efficientad_score_mode_auroc

**Caption**: EfficientAD 15-class score mode AUROC heatmap. Mean AUROC=0.510. All 5 score modes nearly identical. Only tile/carpet > 0.7.
**Use in README**: Yes — Phase 9/10+ 定量工程证据图 section
**Use in Portfolio**: Yes — §5.5C
**Use in Edge Summary**: Yes — §13B.4
**Use in Interview**: Yes — Q4 (EfficientAD gate)
**Boundary**: EfficientAD is a load-shedding gate, not a reliable detector.

## fig08_vlm_quantization_cliff

**Caption**: W8A8 quantization cliff: PC bf16 defect_type_exact=51.8%, Board W8A8=0%. Coarse fields preserved, fine-grained collapsed.
**Use in README**: Yes — Phase 9/10+ 定量工程证据图 section
**Use in Portfolio**: Yes — §5.5C
**Use in Edge Summary**: Yes — §13B.4
**Use in Interview**: Yes — Q3 (VLM 瓶颈)
**Boundary**: Supports engineering decision; does not claim VLM production deployment.

## existing figures (historical)

The 6 existing curated figures (`fig_existing_*`) in `docs/figures/report_charts/existing/` are historical engineering evidence from Phase 8 / VLM AB / board validation. They are used in the `<details>` section of README and in the Atlas/Edge Summary/Portfolio appendices. They serve a complementary role to the 8 new report charts above.
