# Phase 10.1b-5d Soak Runner Production YOLO Fix

**Date**: 2026-05-27
**Branch**: `phase10.1b/live-soak-runner-production-yolo`
**Base**: `b4e0293` (PR #21 merged)

---

## 1. Scope

- Runner/runbook fix only.
- No 200/500 full soak.
- No public snapshot capture.
- No 5d success claim.
- No backend/frontend behavior change.
- No schema change.

---

## 2. Baseline

- PR #21 blocker note merged (`phase10_1b_5d_soak_blocker_note.md`).
- Invalid defect ids 4113-4150 from failed soak (must be excluded).
- Failed root cause: soak runner used random images from all categories, fabricated bboxes/confidence/defect_type via `random.uniform()`, and had `localization_source=None`, `label_source=None`.

---

## 3. Failed Runner Audit

### 3.1 Where the failed script lived

The failed script (`soak_runner.py`) was **server-local only** — created at `/tmp/soak_runner.py` on the public server during the 5d session. It was never committed to the repo.

### 3.2 Why it was unsafe

| Defect | Description |
|--------|-------------|
| No category filter | `get_all_images()` walked `/var/lib/vision-demo/static/defects/` recursively, picking images from ALL 8 MVTec AD categories (capsule, carpet, grid, hazelnut, leather, metal_nut, pill, cable). |
| Mislabeled categories | Assigned `category=metal_nut` or `category=cable` by alternating index (`i % 2`), regardless of actual image content. |
| Fabricated bboxes | `random.uniform()` for x, y, w, h — not from YOLO. |
| Fabricated confidence | `random.uniform(0.5, 0.99)` — not from model. |
| Fabricated defect_type | `random.choice()` from hardcoded list — not from model. |
| No provenance | `localization_source=None`, `label_source=None` in database. |
| No anomaly_score source | `random.uniform(10, 50)` — not from EfficientAD. |

### 3.3 Why random/static/defects sampling is forbidden

The `/var/lib/vision-demo/static/defects/` directory contains uploaded images from ALL categories accumulated across Phases 4-10. Sampling from it blindly:
- Violates the metal_nut + cable category boundary.
- Produces images that don't match their posted category.
- Makes the frontend live stream show mismatched content (e.g. pill labeled as cable).
- Undermines the integrity of any soak metrics.

---

## 4. Corrected Source-of-Truth Design

### 4.1 Trusted source image selection

Source images come from the **curated Phase 10 val dataset** on the RK3588:
```
<VAL_DIR>/datasets/phase10/images/val/
```

This directory contains 59 images with filenames prefixed by category:
- `metal_nut_bent_*.png` (8 images)
- `metal_nut_color_*.png` (7 images)
- `metal_nut_flip_*.png` (7 images)
- `metal_nut_scratch_*.png` (7 images)
- `cable_bent_wire_*.png` (4 images)
- `cable_cable_swap_*.png` (4 images)
- `cable_combined_*.png` (4 images)
- `cable_cut_inner_insulation_*.png` (5 images)
- `cable_cut_outer_insulation_*.png` (3 images)
- `cable_missing_cable_*.png` (4 images)
- `cable_missing_wire_*.png` (3 images)
- `cable_poke_insulation_*.png` (3 images)

Category is inferred from filename prefix (`metal_nut_*` or `cable_*`). All other categories are excluded.

### 4.2 metal_nut/cable-only gate

The runner's `discover_val_images()` function only includes images whose filename starts with `metal_nut` or `cable`. No other categories are possible.

### 4.3 Invalid id exclusion

Defect ids 4113-4150 from the failed soak are documented as invalid and excluded from any future snapshot, metrics, or source pool.

### 4.4 Production YOLO/localizer provenance

All canonical fields come from `ort_localizer.py` — the production ONNX Runtime CPU localizer:

| Field | Source | Value |
|-------|--------|-------|
| `bboxes` | `ort_localizer.py` decode() | Normalized top-left xywh from YOLOv8n output |
| `confidence` | `ort_localizer.py` process_image() | Top detection confidence |
| `defect_type` | `ort_localizer.py` + phase10_classes.yaml | Class name from YOLO class head |
| `category` | `ort_localizer.py` + phase10_classes.yaml | Derived from class name prefix |
| `localization_source` | Runner stamps | `"ort_yolov8n_cpu"` |
| `label_source` | Runner stamps | `"yolo_class_head"` |
| `anomaly_score` | CLI arg (placeholder) | Documented as placeholder; EfficientAD not available in runner context |

---

## 5. Runner Design

### 5.1 Script location

`tools/live_soak/production_yolo_soak_runner.py` — generic, no secrets, no private paths.

### 5.2 Modes

| Mode | Description | POST? | Limit |
|------|-------------|-------|-------|
| `dry-run` | Scan + validate all candidates | No | All |
| `pre-soak` | Dry-run + upload verified candidates | Yes | `--limit` (default 20) |
| `full` | Upload all verified candidates | Yes | All (not used in this fix) |

### 5.3 Validation gates

**Gate A — Source category gate:**
- Only `metal_nut_*` and `cable_*` filenames from curated val directory.
- No sampling from `/var/lib/vision-demo/static/defects/`.
- No random category assignment.

**Gate B — Production inference gate:**
- Every image runs through `ort_localizer.py` subprocess.
- `bboxes` from YOLO decode — refuse upload if empty.
- `confidence` from YOLO — refuse if zero.
- `defect_type` from class YAML — refuse if `"anomaly"` (no detection).
- `category` from YOLO must match source category from filename.
- `localization_source = "ort_yolov8n_cpu"` stamped by runner.
- `label_source = "yolo_class_head"` stamped by runner.

**Gate C — Metadata gate:**
- `anomaly_score` from CLI arg (default 0.0, documented as placeholder).
- `schema_version = "v1"`.
- `variant = "2B_base"`.
- `description` indicates soak test.

**Gate D — Audit gate:**
- Per-image validation table printed before any upload.
- Columns: image basename, source_category, posted_category, defect_type, bbox_count, confidence, anomaly_score, localization_source, label_source, will_upload, reason_if_blocked.
- Dry-run mode fails if ANY candidate is blocked.

### 5.4 Stop conditions

- Dry-run: exit 1 if any candidate blocked.
- Pre-soak: stop after `--limit` uploads, print summary.
- Any upload error: log and continue (don't abort entire soak).
- Enrichment timeout: log and continue.

### 5.5 Post-upload verification

For each uploaded defect, the runner verifies:
- `category` matches source category.
- `defect_type` matches YOLO output.
- `localization_source == "ort_yolov8n_cpu"`.
- `label_source == "yolo_class_head"`.
- `bboxes` non-empty.
- Enrichment reaches terminal state (complete/rejected/failed).

---

## 6. Pre-Soak Validation Result

**Status: NOT RUN**

The pre-soak was not run in this session because:
1. The `ort_localizer.py` script requires `onnxruntime` and the YOLOv8n ONNX model, both of which are on the RK3588 board.
2. The runner is designed to execute on the RK3588 where the model and dataset co-locate.
3. Running the pre-soak requires SSH to the RK3588 and uploading to the public server — this is an execution step, not a docs step.

**Blocker**: Pre-soak execution deferred to a follow-up session that:
1. Deploys the runner script to the RK3588.
2. Runs `--mode dry-run` to validate all 59 candidates.
3. If dry-run passes, runs `--mode pre-soak --limit 10`.
4. Records results in an updated report or new PR.

---

## 7. Safety Checks

| Check | Result |
|-------|--------|
| No random canonical fields | PASS — all from ort_localizer.py |
| No mixed categories | PASS — only metal_nut/cable from curated val dir |
| No use of invalid ids 4113-4150 | PASS — excluded by documentation |
| No secrets/private paths/tokens | PASS — script uses CLI args only |
| No snapshot captured | PASS |
| No full soak run | PASS |
| No backend/frontend changes | PASS |
| No schema changes | PASS |

---

## 8. Decision Gate

**Status: READY FOR DRY-RUN**

The runner script and design are complete. Next step:
1. Deploy `tools/live_soak/production_yolo_soak_runner.py` to RK3588.
2. Run `--mode dry-run` with production model paths.
3. If dry-run passes all 59 candidates, run `--mode pre-soak --limit 10`.
4. If pre-soak passes (all uploads have production YOLO provenance, enrichment completes), proceed to plan 200/500 full soak in a separate execution.

---

## 9. Explicit Not Done

- No 200/500 full soak.
- No public snapshot capture.
- No public demo switch.
- No review pool implementation.
- No backend/frontend behavior change.
- No EDGE_VLM_MODE=http.
- No cloud_vlm.
- No schema changes.
- No YOLO/ORT/RKNN/LoRA model changes.
