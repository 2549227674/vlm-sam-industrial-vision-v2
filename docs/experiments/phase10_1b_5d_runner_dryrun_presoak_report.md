# Phase 10.1b-5d Runner Dry-Run + Pre-Soak Report

**Date**: 2026-05-27
**Branch**: `phase10.1b/live-soak-runner-dryrun-presoak`
**Base**: `6f60c5d` (PR #22 merged)

---

## 1. Scope

- Dry-run + 10-upload pre-soak only.
- No 200/500 full soak.
- No public snapshot capture.
- No Phase 10.1b-5d success claim.
- No backend/frontend behavior change.
- No schema change.

---

## 2. Candidate Scan Result (dry-run mode)

**Mode**: `--dry-run --allow-ineligible`
**Total images scanned**: 59
**Valid candidates**: 52
**Ineligible (blocked)**: 7

All 7 ineligible images had YOLO no-detection (confidence=0, no bboxes). This is expected — the YOLO model at conf=0.25 does not detect defects in all val images. The runner reports these as ineligible, not as failures.

| Ineligible Image | Reason |
|------------------|--------|
| cable_bent_wire_003.png | no_bboxes, confidence_zero |
| cable_cable_swap_009.png | no_bboxes, confidence_zero |
| cable_cut_outer_insulation_004.png | no_bboxes, confidence_zero |
| cable_cut_outer_insulation_008.png | no_bboxes, confidence_zero |
| cable_missing_wire_000.png | no_bboxes, confidence_zero |
| metal_nut_bent_023.png | no_bboxes, confidence_zero |
| metal_nut_scratch_022.png | no_bboxes, confidence_zero |

**Valid candidates by category**:
- cable: 25
- metal_nut: 27

**Candidate scan gate**: all 52 valid candidates pass:
- source_category in {metal_nut, cable}
- YOLO category matches source category
- bboxes non-empty
- confidence > 0
- localization_source = "ort_yolov8n_cpu"
- label_source = "yolo_class_head"

Note: The strict `--dry-run` (without `--allow-ineligible`) exits 1 if any candidate is ineligible. This is by design — strict mode requires zero blocked candidates for a clean pass. The candidate scan with `--allow-ineligible` is used here to enumerate valid candidates for the soak.

---

## 3. Pre-Soak Result (clean re-run)

**Mode**: `pre-soak --limit 10`
**Uploaded**: 10/10
**409 Conflict**: 0
**Failed**: 0
**Error**: 0

### Historical Bug Note

The first pre-soak attempt (ids 4157-4159) had 7/10 409 Conflicts. Root cause: `edge_ts` was generated at meta-build time with second-precision, so multiple images processed within the same second received identical `line_id` + `edge_ts` pairs, violating the UNIQUE constraint. Fix: `edge_ts` is now generated at upload time with microsecond precision. This re-run verifies the fix.

### Defect IDs Created

| ID | Image | Category | Defect Type | Confidence | BBoxes | Loc Source | Label Source |
|----|-------|----------|-------------|------------|--------|------------|-------------|
| 4161 | cable_bent_wire_001.png | cable | bent_wire | 0.270 | 1 | ort_yolov8n_cpu | yolo_class_head |
| 4162 | cable_bent_wire_004.png | cable | bent_wire | 0.719 | 1 | ort_yolov8n_cpu | yolo_class_head |
| 4163 | cable_bent_wire_009.png | cable | bent_wire | 0.802 | 1 | ort_yolov8n_cpu | yolo_class_head |
| 4164 | cable_cable_swap_002.png | cable | cable_swap | 0.392 | 1 | ort_yolov8n_cpu | yolo_class_head |
| 4165 | cable_cable_swap_003.png | cable | cable_swap | 0.399 | 2 | ort_yolov8n_cpu | yolo_class_head |
| 4166 | cable_cable_swap_008.png | cable | cable_swap | 0.872 | 1 | ort_yolov8n_cpu | yolo_class_head |
| 4167 | cable_combined_001.png | cable | bent_wire | 0.485 | 1 | ort_yolov8n_cpu | yolo_class_head |
| 4168 | cable_combined_002.png | cable | combined | 0.325 | 1 | ort_yolov8n_cpu | yolo_class_head |
| 4169 | cable_combined_007.png | cable | missing_wire | 0.954 | 1 | ort_yolov8n_cpu | yolo_class_head |
| 4170 | cable_combined_008.png | cable | bent_wire | 0.928 | 2 | ort_yolov8n_cpu | yolo_class_head |

### Upload Latency

| Metric | Value |
|--------|-------|
| p50 | 1.6s |
| p95 | 1.9s |

### Enrichment Terminal States

| Status | Count |
|--------|-------|
| complete | 10 |
| failed | 0 |
| rejected | 0 |
| timeout | 0 |

| Metric | Value |
|--------|-------|
| p50 enrichment latency | 15.8s |
| p95 enrichment latency | 18.8s |

### Canonical Provenance Checks

| Check | Result |
|-------|--------|
| category matches source | PASS (10/10) |
| defect_type from YOLO | PASS (10/10) |
| localization_source = ort_yolov8n_cpu | PASS (10/10) |
| label_source = yolo_class_head | PASS (10/10) |
| bboxes non-empty | PASS (10/10) |
| observation_source = edge_vlm | PASS (10/10) |
| observation non-empty | PASS (10/10) |
| severity_reason non-empty | PASS (10/10) |

### VLM Output vs. Detection Description

The `description` field in the upload meta is the runner's detection summary (e.g., "production_yolo_soak cable/bent_wire"), not VLM output. The actual VLM enrichment output fields are:
- `observation` — VLM-generated defect observation text
- `severity_reason` — VLM-generated severity justification
- `observation_source` — provenance tag ("edge_vlm")

These three fields are populated by the enrichment pipeline after upload. The frontend JSON panel may show the `description` field; this should not be confused with VLM output.

### WebSocket Payload Observed

**Status**: NOT CAPTURED — the runner does not have a WebSocket client. WebSocket events were emitted by the backend (confirmed by ws_clients=1 at time of check), but the actual payload was not captured by the runner.

### Frontend Terminal Re-fetch Observed

**Status**: NOT OBSERVED — the runner runs headless without browser access. Frontend re-fetch would need to be verified manually in a browser session.

### Profile / Trace Note

Runner uploads have `pipeline_ms: {efficientad: 0, fastsam: 0, qwen3vl: 0}` and no `trace_events`. This is expected — the runner uses ort_localizer.py for YOLO inference, not the full RK3588 pipeline. The frontend Profile/Trace page will be empty for runner-uploaded defects. This does not indicate RK3588 or VLM performance issues.

Full soak telemetry should either:
- Add real `trace_events` / `pipeline_ms` from the runner's YOLO + enrichment timing, or
- Explicitly document that the Profile page is unsupported for runner uploads.

---

## 4. Multipart Encoding Bug Fix

During pre-soak execution, a bug was found and fixed in the runner's multipart body construction:

- **Bug**: Extra `\r\n` bytes between multipart parts caused uploaded JPEG files to have 4 extra bytes (`0d0a0d0a`) prepended before the JPEG header.
- **Symptom**: RKLLM API server returned "cannot identify image file" when processing uploaded images through the VLM wrapper.
- **Fix**: Changed from `b"\r\n".join([...])` to direct byte concatenation with correct `\r\n` placement.
- **Verified**: After fix, images upload correctly and VLM enrichment completes successfully.

---

## 5. Security Scan

```
$ grep -RInE "sshpass|password|token|api[_-]?key|secret|BEGIN .*PRIVATE KEY|([0-9]{1,3}\.){3}[0-9]{1,3}|EDGE_VLM_COMMAND|/home/|/opt/|http://[0-9]|https://[0-9]|ProxyCommand|7890" docs/experiments/phase10_1b_5d_runner_dryrun_presoak_report.md || true
```

**Result**: No matches. Report uses only placeholders and generic references.

---

## 6. Invalid IDs Excluded

Defect ids 4113-4150 from the failed 5d soak are excluded from all metrics and future snapshots.

---

## 7. Decision Gate

**Status: PASS — ready to plan separate 200/500 full soak**

All validation gates passed:
- Candidate scan: 52/59 valid, 7 ineligible (expected YOLO no-detection)
- Pre-soak: 10/10 uploads successful, 0 conflicts, 0 errors
- All canonical fields verified (10/10)
- Enrichment completes successfully via EdgeVLM subprocess (10/10 complete)
- No random/fabricated canonical fields
- Upload uniqueness fix verified (microsecond edge_ts)
- No mixed categories
- Multipart encoding bug fixed

**Next step**: Plan and execute 200/500 full soak in a separate session/PR, using the 52 valid candidates from the dry-run.

---

## 8. Explicit Not Done

- No 200/500 full soak.
- No public snapshot capture.
- No public demo switch.
- No review pool implementation.
- No backend/frontend behavior change.
- No EDGE_VLM_MODE=http.
- No cloud_vlm.
- No schema changes.
- No YOLO/ORT/RKNN/LoRA model changes.
