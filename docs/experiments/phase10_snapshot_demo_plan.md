# Phase 10 v1 Snapshot Demo Plan

## Status: PASS (2026-05-26)

## Deliverables

### 1. Soak Evidence (Engineering Reliability)
- 30-min RK3588 run, metal_nut + cable only
- Metrics recorded in `phase10_ort_integration_plan.md` Gate 2
- Purpose: release gate, not demo artifact

### 2. Phase 10 v1 Localization Snapshot (Demo Artifact)
- Curated from soak test backend records
- 40 records, metal_nut + cable only, 12 defect types
- Real YOLO detections only (confidence > 0, no fallback boxes)
- v1.3 fields: localization_source, label_source, observation_source, pipeline_ms.localizer, T3.localizer trace_events
- Purpose: merge-main / remote frontend static demo

### 3. Phase 10.1 Roadmap Note
- VLM is NOT called in Phase 10 v1
- observation_source="template", severity fixed to "medium"
- observation/severity_reason enrichment is Phase 10.1 scope
- Do not present v1 snapshot as full VLM-enriched inspection pipeline

## Snapshot Files

| File | Description |
|------|-------------|
| `frontend/public/demo-data/phase10_ort_latest/manifest.json` | Metadata + caveats |
| `frontend/public/demo-data/phase10_ort_latest/defects_snapshot.json` | 40 curated records |
| `frontend/public/demo-data/phase10_ort_latest/stats_snapshot.json` | Aggregated stats |
| `frontend/public/demo-data/phase10_ort_latest/images/` | 40 JPEG images |
| `frontend/public/demo-data/phase10_ort_latest/README.md` | Docs |

## Data Composition

- 16 metal_nut detections (bent, color, flip, scratch)
- 24 cable detections (bent_wire, cable_swap, combined, cut_inner_insulation, cut_outer_insulation, missing_cable, missing_wire, poke_insulation)
- All variant="ort_2B", confidence > 0
- Bounding boxes from YOLOv8n-detect (normalized [0,1], center-x/y format)
- Pipeline: EfficientAD → YOLO Localizer → Upload

## Caveats (in manifest.json)

1. ORT CPU fallback, NOT RKNN/NPU. RKNN remains BLOCKED.
2. VLM NOT called. observation_source=template. Enrichment is Phase 10.1.
3. Only metal_nut + cable (12 YOLO classes).
4. pipeline_ms.upload=0.0 (sequencing constraint).

## Frontend Integration

`data-source.ts`: phase10_ort_latest > real_run_latest > mock.
API_BASE built with `NEXT_PUBLIC_API_BASE=https://vision.hanlab.app`.
