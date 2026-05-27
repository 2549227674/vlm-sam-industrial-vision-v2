# Phase 10.1b EdgeVLM Demo Snapshot

Curated from real EdgeVLM smoke validation on RK3588 (Orange Pi 5 Plus, 16GB).

## What this is

- Real async enrichment pipeline: auto-enqueue → worker loop → EdgeVlmProvider subprocess → hallucination guard → denormalize
- 14 records: metal_nut (11) + zipper (3), 1 defect type each (scratch, broken_teeth)
- Qwen3-VL-2B W8A8 on RK3588 NPU for edge_vlm enrichment
- Template fallback for baseline comparison
- All 4 enrichment states represented: complete (9), rejected (3), failed (2)

## What this is NOT

- NOT a production category expansion — non-Phase-10 categories (zipper) are hardware/protocol smoke examples only
- NOT VLM-powered localization — VLM provides narrative observation/severity_reason only
- NOT modifying canonical fields — category, defect_type, confidence, anomaly_score, bboxes are YOLO/ORT-owned and immutable

## Data Sources

| Subset | Source | Description |
|---|---|---|
| metal_nut records (IDs 4154-4172) | vision.db enrichment smoke test | EdgeVlmProvider subprocess validation with fake + real wrappers |
| zipper records (IDs 9000-9002) | Real RK3588 Qwen3-VL-2B smoke | Actual VLM inference on board, documented in smoke report |

## VLM Responsibility

EdgeVLM is **narrative-only**. It may only write:
- `observation` — visual description of the defect area
- `severity_reason` — severity assessment explanation
- `observation_source` — set to `edge_vlm` or `template`

It must **never** modify:
- category, defect_type, confidence, anomaly_score, bboxes
- localization_source, label_source
- Any YOLO/ORT detection output

## Enrichment States in This Snapshot

| State | Count | Meaning |
|---|---|---|
| complete (edge_vlm) | 5 | Real VLM produced valid JSON → guard accepted |
| complete (template) | 4 | Template fallback observation (no VLM call) |
| rejected | 3 | VLM output contained forbidden keys or invalid JSON → guard rejected |
| failed | 2 | Subprocess timeout or image resolution error |

## Contents

- `snapshot_meta.json` — metadata, safety notes, counts
- `defects.json` — 14 curated records with enrichment fields
- `stats.json` — aggregated stats with enrichment breakdown
- `images/` — 14 JPEG images

## Pipeline Timing (VLM enrichment only)

- Median VLM inference: ~12s per job (Qwen3-VL-2B W8A8, including HTTP overhead)
- Median upload POST: <50ms (non-blocking, VLM never called during upload)

## Safety

No real IPs, credentials, private paths, model paths, device paths, usernames, passwords, tokens, API keys, sshpass commands, private keys, or raw EDGE_VLM_COMMAND values are included in this snapshot.
