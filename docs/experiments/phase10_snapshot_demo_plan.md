# Phase 10 ORT Snapshot Demo Plan

## Snapshot Mechanism: PASS (2026-05-26)
## 30-min Soak Test: PENDING (running on RK3588)
## Final Snapshot Source: PRELIMINARY (simulator data; will regenerate from soak records)

## Purpose

Static frontend demo artifact for merge-main / remote server presentation.
Demonstrates Phase 10 ORT CPU fallback integration without requiring a live backend or RK3588.

## Current Status

The snapshot mechanism (data-source.ts fallback, manifest/defects/stats loading, frontend rendering)
is verified PASS. However, the current snapshot data was generated from simulator data before the
30-min soak test completed. It is labeled **PRELIMINARY** in manifest.json and README.md.

After the soak test completes, the snapshot will be regenerated from the actual backend records
uploaded by the RK3588 edge_pipeline during the soak run.

## Files

| File | Description |
|------|-------------|
| `frontend/public/demo-data/phase10_ort_latest/manifest.json` | Snapshot metadata + caveats |
| `frontend/public/demo-data/phase10_ort_latest/defects_snapshot.json` | 20 defect records |
| `frontend/public/demo-data/phase10_ort_latest/stats_snapshot.json` | Aggregated stats |
| `frontend/public/demo-data/phase10_ort_latest/images/` | 20 JPEG images |
| `frontend/public/demo-data/phase10_ort_latest/README.md` | Human-readable docs |

## Data Composition (Preliminary)

- 12 metal_nut detections (bent, color, flip, scratch, etc.)
- 8 cable detections (bent_wire, combined, etc.)
- All variant="ort_2B" with v1.3 source fields
- Bounding boxes from YOLOv8n-detect (normalized [0,1])
- Pipeline: EfficientAD (~18ms) → YOLO Localizer (~188ms) → Upload (~13ms)
- **Source: simulator-generated data, NOT real RK3588 soak run**

## Frontend Integration

`data-source.ts` updated to try `phase10_ort_latest` before `real_run_latest`.
Snapshot tier activates when live API is unreachable (static export / remote demo).

Priority order:
1. Live API (backend running)
2. Phase 10 ORT snapshot (new)
3. Real run latest (existing Phase 9 snapshot)
4. Mock fallback

## Caveats (included in manifest.json)

1. **PRELIMINARY**: Generated from simulator data, not completed soak run.
2. This is ORT CPU fallback, NOT RKNN/NPU deployment. RKNN remains BLOCKED.
3. pipeline_ms.upload is 0.0 in edge payloads (sequencing constraint).
4. VLM is not called — severity fixed to "medium".
5. localization_source="ort_yolov8n_cpu" = ONNX Runtime on CPU, not NPU.
6. Backend auth was temporarily disabled for soak test uploads. Not production config.

## Verification

- Frontend loads snapshot when backend is stopped
- ORT records render with "ort" badge, YOLO Localizer Gantt bar
- BBox overlays visible on metal_nut and cable images
- Stats show ort_2B in ab_compare

## Post-Soak Actions

After 30-min soak test completes:
1. Collect final metrics from Orange Pi logs and droplet backend
2. Regenerate snapshot from droplet backend records
3. Update manifest with soak run_id, duration, and real metrics
4. Remove "PRELIMINARY" labels
5. Re-enable backend auth
