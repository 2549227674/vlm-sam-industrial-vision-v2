# Phase 10.1b-5d Live Stream Soak — BLOCKER NOTE

**Date**: 2026-05-27
**Branch**: `phase10.1b/live-stream-soak-execution`
**Status**: **BLOCKED — soak halted at 38/200 uploads**

---

## 1. What Happened

A 200-upload soak was started using a Python script (`soak_runner.py`) on the public server. The script was halted after 38 uploads when visual inspection of the frontend live stream revealed non-allowed category images appearing with `category=cable` or `category=metal_nut`.

---

## 2. Root Cause

The soak script had **three critical defects**:

### 2.1 No Category Filter on Source Images

The script picked random images from `/var/lib/vision-demo/static/defects/`, which contains images from **all 8 previously uploaded MVTec AD categories**: capsule, carpet, grid, hazelnut, leather, metal_nut, pill, cable.

It then assigned `category=metal_nut` or `category=cable` in the upload meta JSON, **regardless of what the actual image showed**. Result: pill/capsule/carpet images appeared in the frontend live stream labeled as `cable` or `metal_nut`.

### 2.2 Fabricated BBoxes (Not Production YOLO)

The script generated **random bounding boxes** with `random.uniform()`:
```python
bbox = [{"x": random.uniform(0.1, 0.6),
         "y": random.uniform(0.1, 0.6),
         "w": random.uniform(0.05, 0.2),
         "h": random.uniform(0.05, 0.2)}]
```

These are not from the production YOLO localizer. The `localization_source` and `label_source` fields were set to `None` in the database.

### 2.3 Fabricated Confidence and Defect Type

Confidence was `random.uniform(0.5, 0.99)` and defect_type was randomly chosen from a hardcoded list. Neither came from actual model inference.

---

## 3. Audit Table (Last 20 Soak Uploads)

| id | posted category | posted defect_type | bbox count | bbox source | loc_source | label_source |
|----|----------------|-------------------|------------|-------------|------------|-------------|
| 4131 | metal_nut | flip | 1 | RANDOM | None | None |
| 4132 | cable | poke_insulation | 1 | RANDOM | None | None |
| 4133 | metal_nut | bent | 1 | RANDOM | None | None |
| 4134 | cable | cable_swap | 1 | RANDOM | None | None |
| 4135 | metal_nut | color | 1 | RANDOM | None | None |
| 4136 | cable | missing_cable | 1 | RANDOM | None | None |
| 4137 | metal_nut | bent | 1 | RANDOM | None | None |
| 4138 | cable | missing_cable | 1 | RANDOM | None | None |
| 4139 | metal_nut | color | 1 | RANDOM | None | None |
| 4140 | cable | cable_swap | 1 | RANDOM | None | None |
| 4141 | metal_nut | bent | 1 | RANDOM | None | None |
| 4142 | cable | cable_swap | 1 | RANDOM | None | None |
| 4143 | metal_nut | bent | 1 | RANDOM | None | None |
| 4144 | cable | cable_swap | 1 | RANDOM | None | None |
| 4145 | metal_nut | scratch | 1 | RANDOM | None | None |
| 4146 | cable | poke_insulation | 1 | RANDOM | None | None |
| 4147 | metal_nut | color | 1 | RANDOM | None | None |
| 4148 | cable | cable_swap | 1 | RANDOM | None | None |
| 4149 | metal_nut | bent | 1 | RANDOM | None | None |
| 4150 | cable | cable_swap | 1 | RANDOM | None | None |

**All 38 soak uploads** have:
- `localization_source = None` (no production YOLO)
- `label_source = None` (no production YOLO)
- `bboxes` = random fabricated values
- Source images = random from ALL categories (not filtered to metal_nut/cable)

---

## 4. Impact

- **38 invalid defects** uploaded to the public server database (ids 4113-4150)
- **38 enrichments** completed with `observation_source=edge_vlm` on invalid data
- Frontend live stream showed mismatched category images
- No data corruption to pre-existing defects (canonical fields on pre-soak data unchanged)

---

## 5. Cleanup Required

The 38 soak defects (ids 4113-4150) must be excluded from any future snapshot. They are invalid because:
1. Source images are not from the posted category
2. BBoxes are not from production YOLO
3. Confidence/defect_type are fabricated

---

## 6. What Must Change Before Resuming

The soak script must be rewritten to:

1. **Use only metal_nut and cable source images** — filter by the original defect's category in the database, not by filename pattern
2. **Run production YOLO localizer** on each image before POST — bboxes, confidence, defect_type, localization_source, label_source must come from actual model output
3. **Not fabricate any metadata** — all fields must be sourced from real inference
4. **Verify category matches image content** — the posted category must match the source image's actual class

---

## 7. Decision

**5d soak is BLOCKED.** Cannot resume until:
- Soak script uses production YOLO output for bboxes/category/defect_type/confidence
- Source images are filtered to metal_nut + cable only
- Pre-soak of 10-20 uploads shows: only metal_nut/cable images, category matches source, bbox source is production YOLO, no pill/zipper/screw images
- Canonical fields are not hardcoded placeholders

No passing 5d report. No public snapshot capture. No PR.
