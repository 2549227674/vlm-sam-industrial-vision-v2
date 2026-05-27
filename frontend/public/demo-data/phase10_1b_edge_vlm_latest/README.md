# Phase 10.1b EdgeVLM Demo Snapshot — Artifact Export Pending

> Status: **snapshot packaging deferred — real artifacts not locally available**
> Date: 2026-05-27

## What this directory is for

This directory is the designated location for a demo snapshot showcasing real RK3588 EdgeVLM async enrichment results.

## Why the snapshot is not yet packaged

The real RK3588 EdgeVLM smoke validation (PR #13, `docs/experiments/phase10_1b_real_rk3588_edge_vlm_smoke_report.md`) was run against a temporary SQLite database (`/tmp/vlm_smoke_test.db`) and temporary test images (`/tmp/vlm_validation_scripts/`). These artifacts were cleaned up after validation and are no longer available locally.

**Missing artifacts required to build the snapshot:**

| Artifact | Status | How to regenerate |
|---|---|---|
| `defects.json` with real VLM observation/severity_reason | Lost (temp DB) | Re-run R2/R8 smoke scenarios with the real EdgeVLM wrapper on RK3588, then export defect + enrichment records |
| JPEG images submitted to backend during smoke | Lost (temp files) | Convert MVTec source PNGs to JPEG, or re-upload during smoke run |
| Enrichment records with timestamps | Lost (temp DB) | Re-run smoke, then query `GET /api/defects/{id}/enrichment` for each defect |
| `stats.json` aggregation | Derived from above | Re-derive from exported defect/enrichment records |

## What was validated (documented in smoke report)

The smoke validation confirmed:

- **R1**: Real Qwen3-VL-2B W8A8 inference returns valid 3-key JSON (observation, severity_reason, accepted_box_ids)
- **R2**: Full pipeline: defect → auto-enqueue → worker → real VLM → complete, canonical fields unchanged
- **R3**: Forbidden key defense correctly rejected
- **R4**: Bad JSON correctly rejected
- **R5**: Timeout correctly failed
- **R6**: Nonzero exit correctly failed
- **R7**: Upload path non-blocking (24ms POST, no VLM blocking)
- **R8**: 3 sequential VLM jobs all completed
- **R9**: Ineligible defects (empty bboxes, zero confidence) not enqueued
- **R10**: Backend restart clean, data persisted

## Real VLM outputs captured (for future snapshot reconstruction)

### R1 — pill/faulty_imprint

```json
{
  "observation": "A white oval pill has a faulty imprint of 'FF' on its surface. The impression is not clearly defined and appears to be partially obscured or misaligned.",
  "severity_reason": "The imprinted text is significantly blurred and does not form the intended characters, which may affect drug identification and safety in clinical settings.",
  "accepted_box_ids": [0]
}
```

### R1 — screw/scratch

```json
{
  "observation": "A screw with a scratch on its shaft.",
  "severity_reason": "The defect is located on the body of the screw and appears to be a continuous line that may affect functionality or appearance. The confidence level for this detection is high, indicating it's likely an accurate identification.",
  "accepted_box_ids": [0]
}
```

### R2 — zipper/broken_teeth (full pipeline)

```json
{
  "observation": "A close-up of a black zipper on fabric material showing a broken tooth.",
  "severity_reason": "The zipper has a clear defect where one of its teeth is missing or damaged. This damage appears as a break in the chain-like structure, indicating a manufacturing or wear issue that affects functionality.",
  "accepted_box_ids": [0],
  "_canonical_fields": {
    "category": "zipper",
    "defect_type": "broken_teeth",
    "confidence": 0.91,
    "anomaly_score": 0.55,
    "observation_source": "edge_vlm",
    "localization_source": "ort_yolov8n_cpu",
    "label_source": "yolo_class_head"
  }
}
```

## How to rebuild this snapshot

1. Ensure RK3588 board is reachable and RKLLM API Server is running with Qwen3-VL-2B
2. Create local wrapper at `/tmp/vlm_validation_scripts/edge_vlm_wrapper.py` (see smoke report for protocol)
3. Start backend with `ENRICHMENT_PROVIDER=edge_vlm` and real `EDGE_VLM_COMMAND`
4. Run R2/R8 scenarios from the smoke report
5. Export defect records: `GET /api/defects?page_size=100`
6. Export enrichment records: `GET /api/defects/{id}/enrichment` for each
7. Copy submitted images from `backend/static/defects/`
8. Package into `defects.json`, `stats.json`, `manifest.json`, `images/`
9. Verify: no credentials, no private paths, canonical fields unchanged

## Production category note

Non-Phase-10 categories (pill, screw, zipper) were used for hardware/protocol smoke only. This does not expand the production category set (metal_nut + cable). No YOLO/ORT label-space, schema, frontend snapshot, or category expansion is included.

## Safety

No real IPs, credentials, private paths, model paths, device paths, usernames, passwords, tokens, API keys, sshpass commands, private keys, or raw EDGE_VLM_COMMAND values are included in this directory.
