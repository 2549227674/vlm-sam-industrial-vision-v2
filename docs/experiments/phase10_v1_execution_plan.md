# Phase 10 v1 Execution Plan — Localization Refactor

> Branch: `phase10/localization-refactor-v1`
> Primary spec: `phase10_localization_refactor_review_and_final_plan.md`
> Reference: `compass_artifact_wf-6db7af29-ece3-4549-9bfd-c266cf231270_text_markdown.md`
> Scope: **metal_nut + cable** (2 categories, 12 defect types). capsule deferred.

---

## 1. Phase 10 v1 Minimum Goal

**Stop presenting FastSAM/VLM proposals as user-visible localization. Introduce a supervised YOLOv8n-detect localizer for `metal_nut + cable`, with `defect_type` sourced from YOLO class head and `bboxes` / `confidence` from YOLO detector output.**

Concrete deliverables:
1. MVTec GT mask → YOLO label conversion scripts + visual QA.
2. PC-side YOLOv8n-detect training on `metal_nut + cable` (12 classes).
3. ONNX export + RKNN conversion scripts (FP16 primary, INT8 optional).
4. C++ `localizer_worker.cpp` integrated into T3 (replacing FastSAM's primary role).
5. VLM demoted to async observation generator (template first, no bbox/defect_type output).
6. API contract bumped to v1.3 with `localization_source` / `observation_source` fields.
7. Frontend overlay distinguishes model bbox vs proposal vs GT reference.
8. Documentation: supervised POC caveat, per-class metrics, honesty framing.

**NOT in scope for v1:**
- YOLOv8n-seg / U-Net segmentation.
- Cloud VLM enrichment backend route.
- `capsule` category (stretch goal after PC baseline proves viable).
- Edge VLM async observation (template-only for v1 demo).

---

## 1.5 Training Compute / AutoDL Prerequisites

Phase 10 v1 is **not purely a code-refactor task** — it requires actual model training. The following steps need GPU compute:

| Step | Compute Need | Where |
|---|---|---|
| MVTec GT mask → YOLO labels | CPU only | Local (WSL) |
| YOLOv8n-detect training (12 classes, 640², ~100 epochs) | 1× GPU (≥8 GB VRAM) | Local GPU or AutoDL |
| PC validation metrics (mAP, per-class AP, confusion matrix) | GPU (inference only) | Same as training |
| ONNX export | CPU/GPU | Same as training |
| RKNN conversion (rknn-toolkit2) | CPU (WSL or remote) | Local `.venv_rknn` or AutoDL |
| ONNX vs RKNN comparison | CPU | Local |

### Resource Options

**Option A — Local GPU (if available):**
- Requirements: NVIDIA GPU with ≥8 GB VRAM, CUDA 11.8+, Python 3.10+
- Training time estimate: ~30–60 min for YOLOv8n on 12 classes, ~200 images
- No extra setup needed beyond `pip install ultralytics`

**Option B — AutoDL / Remote GPU:**
- User must provide SSH access configuration
- Recommended: configure `~/.ssh/config` on local machine:

```
Host autodl-phase10
    HostName <autoDL-provided-ip>
    Port <autoDL-provided-port>
    User root
    IdentityFile ~/.ssh/id_autodl
```

- **Do NOT commit SSH passwords, private keys, tokens, or AutoDL credentials to the repository.**
- Documentation uses placeholder `autodl-phase10` — user fills in real values locally.

### Information Needed from User Before Training

**[CLAUDE AGENT INSTRUCTION]** When executing Phase 10 and about to start any AutoDL-dependent training task (YOLOv8n training, RKNN conversion on remote, etc.), **STOP and ask the user** to provide the SSH connection information listed below. Do NOT assume or guess any credentials. The user should send their SSH config or connection details in the chat before proceeding with remote operations.

| Item | Placeholder | Example |
|---|---|---|
| SSH host alias | `autodl-phase10` | `autodl-phase10` |
| Remote repo path | `/root/vlm-sam-industrial-vision-v2` | `/root/vlm-sam-industrial-vision-v2` |
| Remote dataset path | `/root/autodl-tmp/mvtec` | `/root/autodl-tmp/mvtec` |
| Conda/env name | `phase10` | `yolo` |
| GPU type | (auto-detected) | RTX 4090 48GB |
| Output/checkpoint path | `/root/autodl-tmp/phase10_runs/` | `/root/autodl-tmp/phase10_runs/` |

### Training Data Flow

```
Local WSL:
  scripts/phase10/mvtec_mask_to_yolo.py → YOLO label .txt files
  scripts/phase10/split_mvtec_localization.py → train/val splits
  scripts/phase10/visualize_yolo_labels.py → QA images

↓ SCP or rsync to remote

Remote (AutoDL / local GPU):
  yolo detect train data=phase10.yaml model=yolov8n.pt ...
  → best.pt, metrics.json

↓ SCP back to local

Local WSL:
  yolo export format=onnx → yolov8n_phase10.onnx
  scripts/phase10/eval_yolo_localization.py → mAP report
  scripts/phase10/compare_onnx_rknn.py → RKNN delta report
```

---

## 2. New Files to Create

### 2.1 Scripts — Data Pipeline (`scripts/phase10/`)

| File | Purpose |
|---|---|
| `scripts/phase10/mvtec_mask_to_yolo.py` | MVTec GT mask → YOLO center-xywh normalized labels. Handles multi-component masks, area filtering, padding. |
| `scripts/phase10/split_mvtec_localization.py` | Stratified 70/30 train/val split from MVTec test images. Outputs `splits/phase10_train.txt`, `splits/phase10_val.txt`. |
| `scripts/phase10/visualize_yolo_labels.py` | Debug visualization: original image + GT mask + generated bbox overlay. Human QA tool. |
| `scripts/phase10/eval_yolo_localization.py` | PC-side evaluation: mAP@0.5, per-class AP, confusion matrix, bbox IoU distribution. |
| `scripts/phase10/compare_onnx_rknn.py` | Compare PyTorch vs ONNX vs RKNN outputs on held-out images. Reports per-class AP delta. |
| `scripts/phase10/report_metrics.py` | Generate per-class metrics table + error gallery HTML. |

### 2.2 Configs

| File | Purpose |
|---|---|
| `configs/phase10_classes.yaml` | Flat class map: `0: metal_nut/bent, 1: metal_nut/color, ... 11: cable/poke_insulation`. |
| `configs/phase10_yolov8n.yaml` | YOLOv8n training hyperparameters (imgsz=640, epochs=100, batch=16, seed=42). |
| `edge/config_phase10_yolo.yaml` | Edge config with YOLO localizer paths, FastSAM disabled, VLM async mode. |

### 2.3 Edge C++ (`edge/src/`)

| File | Purpose |
|---|---|
| `edge/src/pipeline/localizer_worker.cpp` | YOLOv8n-detect RKNN inference worker. Replaces FastSAM as primary bbox source. |
| `edge/include/edge/pipeline/localizer_worker.hpp` | Header for localizer worker. |
| `edge/include/edge/common/localizer_types.hpp` | `LocalizerDetection` struct: `{bbox, class_id, class_label, score}`. |

### 2.4 Backend

| File | Purpose |
|---|---|
| (no new files — modify existing) | |

### 2.5 Frontend

| File | Purpose |
|---|---|
| (no new files — modify existing components) | |

### 2.6 Documentation

| File | Purpose |
|---|---|
| `docs/experiments/phase10_dataset_manifest.md` | Dataset split manifest, per-class sample counts, filter rules. |
| `docs/experiments/phase10_training_runs.md` | Training config, seed, metrics per run. |
| `docs/experiments/phase10_localization_demo_report.md` | Final report: per-class AP, IoU, latency, HTTP 400 count. |

---

## 3. Files to Modify

### 3.1 Backend Schema (`backend/app/schemas/defect.py`)

**Purpose:** Bump to API v1.3 — add source fields, relax `pipeline_ms` stages, keep `bboxes` as primary localizer output.

Changes:
- Add `StageLocalizer = Literal["efficientad", "localizer", "upload", "enrichment"]` (new stage enum).
- Add optional fields to `DefectCreate`:
  - `localization_source: str | None` (e.g. `"yolov8n_detect_rknn"`)
  - `label_source: str | None` (e.g. `"yolo_class_head"`)
  - `observation_source: str | None` (e.g. `"template"`, `"edge_vlm"`, `"cloud_vlm"`, `"human"`)
  - `defect_family: str | None` (e.g. `"insulation_damage"`)
  - `severity_reason: str | None`
  - `observation: str | None` (replaces `description` semantics; `description` kept for backward compat)
- Modify `pipeline_ms` validator: accept both old `{"efficientad","fastsam","qwen3vl"}` and new `{"efficientad","localizer","upload"}` stages. Short-term compat hack: if `fastsam` key present but `localizer` not, treat `fastsam` value as `localizer` latency. Document this as deprecated.
- `schema_version` stays `"v1"` — no bump to `v2`.

### 3.2 API Contract (`docs/API_CONTRACT.md`)

**Purpose:** Document v1.3 changes.

Changes:
- Add v1.3 changelog section.
- Document new optional fields.
- Document `pipeline_ms` stage compatibility rules.
- Document `bboxes` semantic change: now primary localizer output, not FastSAM/VLM proposal.

### 3.3 Backend Route (`backend/app/routers/edge.py`)

**Purpose:** Accept new fields, pass through to DB.

Changes:
- No validation logic changes needed beyond schema — Pydantic handles it.
- Update any hardcoded stage references in stats aggregation.

### 3.4 Backend Stats (`backend/app/routers/stats.py`)

**Purpose:** Add `avg_localizer_ms` to stats aggregation (alongside existing `avg_pipeline_ms`).

### 3.5 Backend DB Model (`backend/app/models/defect.py`)

**Purpose:** Add new columns for `localization_source`, `observation_source`, `defect_family`, `observation`, `severity_reason`.

**DB Migration Note:** This project uses SQLite (WAL mode) for dev/demo. There are two migration strategies:
1. **Dev reset (recommended for v1):** Delete `backend/vision.db`, restart server — SQLAlchemy `create_all()` creates tables with new columns. Acceptable because dev DB has no production data.
2. **Alembic migration (if preserving data):** `alembic revision --autogenerate -m "phase10_source_fields"` → `alembic upgrade head`. Only needed if existing dev DB data must be preserved.

For Phase 10 v1, **option 1 (dev reset) is sufficient**. Alembic setup is deferred to production readiness.

### 3.6 Edge Types (`edge/include/edge/common/types.hpp`)

**Purpose:** Extend `VlmReport` with source fields.

Changes to `VlmReport`:
- Add `std::string localization_source;` (default `"yolov8n_detect_rknn"`)
- Add `std::string label_source;` (default `"yolo_class_head"`)
- Add `std::string observation_source;` (default `"template"`)
- Add `std::string defect_family;`
- Add `std::string severity_reason;`
- Add `std::string observation;` (replaces `description` in new pipeline)
- Rename `PipelineMs::fastsam` → `PipelineMs::localizer` (keep `fastsam` as alias for backward compat)

### 3.7 Edge Upload Worker (`edge/src/upload/upload_worker.cpp`)

**Purpose:** Serialize new fields in JSON payload.

Changes:
- Add `localization_source`, `label_source`, `observation_source`, `defect_family`, `observation`, `severity_reason` to `build_meta_json()`.
- Add `localizer` key to `pipeline_ms` JSON (or map `fastsam` → `localizer`).

### 3.8 Edge Config (`edge/config.yaml`)

**Purpose:** Add YOLO localizer config section.

Changes:
- Add `localizer_model_path`, `localizer_input_size: 640`, `localizer_conf_threshold: 0.25`, `localizer_nms_threshold: 0.45`.
- Add `fastsam_enabled: false` (disabled by default).
- Add `vlm_enabled: false` (VLM completely disabled in v1 — template observation used instead). Edge/cloud VLM async enrichment is Phase 10.1.
- Keep all existing EfficientAD config (gate role unchanged).

### 3.9 Frontend Types (`frontend/src/types/defect.ts`)

**Purpose:** Add new fields to `DefectRead` interface.

Changes:
- Add optional `localization_source?: string`
- Add optional `label_source?: string`
- Add optional `observation_source?: string`
- Add optional `defect_family?: string`
- Add optional `severity_reason?: string`
- Add optional `observation?: string`
- Add optional `object_proposals?: BBox[]` (debug, from FastSAM)
- Add optional `gt_reference_bboxes?: BBox[]` (eval only)

### 3.10 Frontend FrameInspector (`frontend/src/components/v4/FrameInspector.tsx`)

**Purpose:** Update overlay to show source-aware bbox labels.

Changes:
- Bbox tooltip: change from `"Proposal bbox from FastSAM/VLM"` to `"Model bbox from YOLOv8n localizer"` when `localization_source === "yolov8n_detect_rknn"`.
- Add debug toggle for `object_proposals` overlay (hidden by default).
- Add eval-mode toggle for `gt_reference_bboxes` overlay (only visible in snapshot mode).
- Defect type badge: show source annotation `(source: YOLO)` vs `(source: VLM)`.

### 3.11 Frontend CaveatBanner (`frontend/src/components/v4/CaveatBanner.tsx`)

**Purpose:** Add Phase 10 supervised localizer caveat.

Changes:
- Add new caveat item:
  - ZH: "Phase 10 使用 MVTec GT mask 训练的有监督定位器，非标准无监督 benchmark。"
  - EN: "Phase 10 localizer is supervised-trained from MVTec GT masks, not the standard unsupervised benchmark."
- Keep existing Phase 9 caveats for historical mode.

### 3.12 Frontend DataSource (`frontend/src/lib/data-source.ts`)

**Purpose:** Add `phase10_localizer_snapshot` source preset.

Changes:
- Add new preset for Phase 10 snapshot data.
- Distinguish from historical Phase 9 `real_run_latest` snapshot.

### 3.13 Simulator (`simulator/line_runner.py`)

**Purpose:** Update mock payload to match v1.3 schema.

Changes:
- Include new optional fields (`localization_source`, `label_source`, `observation_source`, etc.) in mock `DefectCreate`.
- Update `pipeline_ms` to use `localizer` stage key.

### 3.14 Contract Tests (`backend/tests/contract/`)

**Purpose:** Verify v1.3 schema accepts new fields and rejects invalid ones.

Changes:
- Add test: POST with `localization_source="yolov8n_detect_rknn"` succeeds.
- Add test: POST with old `pipeline_ms` (containing `fastsam` key) still works (backward compat).
- Add test: POST with new `pipeline_ms` (containing `localizer` key) works.
- Update existing tests to use new fields where appropriate.

---

## 4. Modification Purpose Summary

| File | Why |
|---|---|
| `backend/app/schemas/defect.py` | v1.3 schema: source fields, relaxed stages |
| `docs/API_CONTRACT.md` | Document v1.3 contract changes |
| `backend/app/routers/edge.py` | Accept new fields |
| `backend/app/routers/stats.py` | Aggregate localizer latency |
| `backend/app/models/defect.py` | DB columns for new fields |
| `edge/include/edge/common/types.hpp` | VlmReport source fields |
| `edge/src/upload/upload_worker.cpp` | Serialize new fields |
| `edge/config.yaml` | YOLO localizer config |
| `frontend/src/types/defect.ts` | TypeScript types for new fields |
| `frontend/src/components/v4/FrameInspector.tsx` | Source-aware overlay labels |
| `frontend/src/components/v4/CaveatBanner.tsx` | Phase 10 honesty caveat |
| `frontend/src/lib/data-source.ts` | Phase 10 snapshot preset |
| `simulator/line_runner.py` | v1.3 mock payload |
| `backend/tests/contract/` | v1.3 contract tests |

---

## 5. Files NOT Modified and Why

| File | Reason |
|---|---|
| `edge/src/pipeline/ead_worker.cpp` | EfficientAD role unchanged (gate/score/diagnostic). No code change needed. |
| `edge/src/vlm/qwen3vl_runner.cpp` | **Not modified in v1.** VLM prompt change (remove bbox/defect_type) is Phase 10.1 async work. For v1, VLM is simply not called in main path (template observation replaces it). |
| `edge/src/pipeline/fastsam_worker.cpp` | **Not deleted, just disabled via config.** Code stays for debug profile. |
| `edge/src/capture/` | T1 capture logic unchanged. |
| `backend/app/main.py` | No structural changes needed. |
| `backend/app/db.py` | No changes — new columns added via model. |
| `backend/app/ws/manager.py` | WebSocket logic unchanged. |
| `frontend/app/page.tsx` | No structural changes — data flows through existing hooks. |
| `frontend/src/components/v4/CaveatBanner.tsx` | (Modified, listed above) |
| `scripts/mvtec_mask_to_json.py` | **Not modified.** Phase 10 uses new `mvtec_mask_to_yolo.py` instead. Old script stays for VLM LoRA data generation. |
| `scripts/eval_ab_test.py` | **Not modified in v1.** The IoU coordinate confusion (center vs top-left) is documented but fixing this script is separate work. Phase 10 uses new `eval_yolo_localization.py`. |
| `scripts/format_llama_factory_data.py` | Unchanged — still used for VLM LoRA data. |
| `scripts/split_lora_data.py` | Unchanged — still used for VLM eval split. |
| `edge/third_party/` | Unchanged. |
| `frontend/src/components/v4/primitives.tsx` | Unchanged — SevPill, CatPill, etc. reused as-is. |

---

## 6. Module Disposition: Keep / Downgrade / Delete

| Module | Disposition | Rationale |
|---|---|---|
| **EfficientAD-S** (T2) | **Keep, unchanged role** | Gate/score/diagnostic. Not a localizer. Phase 10 does not change its code or config. |
| **FastSAM** (T3 old) | **Downgrade: disabled by default** | `fastsam_enabled: false` in config. Code retained for debug profile. Not deleted. |
| **Qwen3-VL 2B/4B** (T3 old) | **Downgrade: template-only for v1** | VLM is **not called** in v1 main pipeline. `observation` field is a simple template string (e.g. "metal_nut scratch detected") generated by the localizer worker — no VLM inference, no GPU cost. Edge VLM async observation and cloud VLM enrichment are Phase 10.1, not blocking v1. |
| **VLM bbox output** | **Deleted from pipeline** | `bboxes` in report now come exclusively from YOLO localizer. VLM prompt no longer requests bbox. |
| **VLM defect_type output** | **Deleted from pipeline** | `defect_type` now comes from YOLO class head. VLM can describe in natural language but does not set canonical label. |
| **VLM confidence** | **Deleted from pipeline** | `confidence` now is YOLO detection score. |
| **Frontend bbox overlay** | **Retained and enhanced** | Same SVG overlay, but labels and colors now source-aware. |
| **trace_events** | **Retained, extended** | Add `yolo_localizer` trace stage. |
| **Contract tests** | **Retained, extended** | Add v1.3 test cases. |
| **Phase 9 curated snapshot** | **Archived** | Kept as `real_run_latest/` for historical reference. Phase 10 creates new snapshot. |

---

## 7. API Contract: v1.3 (Minimal Evolution, Not v2)

**Decision: Bump to v1.3, not v2.**

Rationale:
- v1.2 fields (`bboxes`, `defect_type`, `confidence`, `description`) all remain — semantics change, not schema.
- New fields are all optional — no breaking changes.
- `pipeline_ms` accepts both old and new stage keys (backward compat).
- `schema_version` stays `"v1"`.

v1.3 additions:
```json
{
  "localization_source": "yolov8n_detect_rknn",
  "label_source": "yolo_class_head",
  "observation_source": "template",
  "defect_family": "insulation_damage",
  "observation": "线缆外层绝缘局部切开",
  "severity_reason": "缺陷区域较集中"
}
```

**Field source clarification:**
- `defect_type`: from YOLO class head (e.g. `"cable/cut_outer_insulation"` → class id → mapped string)
- `bboxes`: from YOLO detector output (post-NMS decoded coordinates, not from class head)
- `confidence`: from YOLO detection score (not from class head)
- `category`: derived from YOLO class prefix (e.g. `"cable/cut_outer_insulation"` → `"cable"`)
- `observation`: template string in v1 (no VLM involved). Edge/cloud VLM async enrichment is Phase 10.1.

v1.3 `pipeline_ms` compatibility:
- New: `{"efficientad": 12.3, "localizer": 24.1, "upload": 5.0}`
- Old (accepted with deprecation warning): `{"efficientad": 12.3, "fastsam": 24.1, "qwen3vl": 0.0}`
- Backend maps `fastsam` → `localizer` latency when `localizer` key missing.

---

## 8. Frontend Overlay: Three-Layer Bbox Distinction

### Visual Design

| Layer | Default Visible | Color | Label | When Shown |
|---|---|---|---|---|
| **Model bbox** (YOLO localizer) | Yes | `var(--acc)` blue | `Localizer: {defect_type} {confidence}%` | Always |
| **Debug proposal** (FastSAM/VLM historical) | No (toggle) | `var(--warn)` orange | `Proposal: FastSAM/VLM` | Debug toggle ON |
| **GT reference** (evaluation only) | No (toggle) | `var(--ok)` green | `GT reference (not model output)` | Snapshot/eval mode toggle ON |

### Implementation in `FrameInspector.tsx`

```tsx
// Model bbox — primary overlay
{defect.bboxes.map((b, i) => (
  <g key={i}>
    <rect ... stroke="var(--acc)" />
    <foreignObject ...>
      <span title="Model bbox from YOLOv8n localizer">
        {defect.defect_type} {defect.confidence * 100}%
      </span>
    </foreignObject>
  </g>
))}

// Debug proposals — optional overlay (hidden by default)
{showProposals && defect.object_proposals?.map((b, i) => (
  <rect key={i} ... stroke="var(--warn)" strokeDasharray="2" />
))}

// GT reference — eval mode only
{showGtRef && defect.gt_reference_bboxes?.map((b, i) => (
  <rect key={i} ... stroke="var(--ok)" strokeDasharray="4" />
))}
```

### Source Annotation in Defect Card

```
Defect Type: cable/cut_outer_insulation (source: YOLO class head)
Observation: 线缆外层绝缘局部切开 (source: template)
Confidence: 0.87 (source: YOLO detection score)
Anomaly Score: 99.84 (source: EfficientAD raw_score)
```

---

## 9. YOLO Data Conversion Script: Input/Output Format

### Input: MVTec Directory Structure

```
simulator/mvtec/
├── metal_nut/
│   ├── test/
│   │   ├── bent/        # 25 images
│   │   ├── color/       # 22 images
│   │   ├── flip/        # 23 images
│   │   ├── scratch/     # 23 images
│   │   └── good/        # good images (not used for bbox labels)
│   └── ground_truth/
│       ├── bent/        # 25 *_mask.png
│       ├── color/       # 22 *_mask.png
│       ├── flip/        # 23 *_mask.png
│       └── scratch/     # 23 *_mask.png
└── cable/
    ├── test/
    │   ├── bent_wire/   # 7 images
    │   ├── cable_swap/  # 12 images
    │   └── ...          # 8 defect types
    └── ground_truth/
        ├── bent_wire/   # 7 *_mask.png
        └── ...
```

### Output: YOLO Label Format

```
datasets/phase10/
├── images/
│   ├── train/    # 70% of defect images
│   └── val/      # 30% of defect images
├── labels/
│   ├── train/    # .txt files, one per image
│   └── val/
└── phase10.yaml  # YOLO dataset config
```

Label `.txt` format (YOLO center-xywh normalized):
```
<class_id> <cx> <cy> <w> <h>
```

Example for `metal_nut/scratch/000.png`:
```
3 0.512 0.487 0.234 0.156
```

### Class Map (`configs/phase10_classes.yaml`)

```yaml
names:
  0: metal_nut/bent
  1: metal_nut/color
  2: metal_nut/flip
  3: metal_nut/scratch
  4: cable/bent_wire
  5: cable/cable_swap
  6: cable/combined
  7: cable/cut_inner_insulation
  8: cable/cut_outer_insulation
  9: cable/missing_cable
  10: cable/missing_wire
  11: cable/poke_insulation
```

### Conversion Logic (`mvtec_mask_to_yolo.py`)

```
For each category in [metal_nut, cable]:
  For each defect_type in category's defect types:
    For each *_mask.png in ground_truth/{defect_type}/:
      1. Read mask, threshold > 0 → binary
      2. connectedComponentsWithStats (8-connected)
      3. For each component:
         - Filter if area < 16 px²
         - Compute xyxy bbox
         - Pad by max(3, 0.02 * max(w, h)) px
         - Clamp to image boundaries
         - Convert to center-xywh normalized
      4. Write class_id cx cy w h to label file
      5. class_id = flat_map[category/defect_type]
```

### Coordinate Convention Contract

| Context | Format | Example |
|---|---|---|
| YOLO label file | center-xywh normalized | `3 0.512 0.487 0.234 0.156` |
| API payload (`bboxes`) | top-left-xywh normalized | `{"x": 0.395, "y": 0.409, "w": 0.234, "h": 0.156}` |
| Frontend SVG overlay | top-left-xywh (as % of 100) | `x=39.5 y=40.9 w=23.4 h=15.6` |
| YOLO post-processing (C++) | center-xywh → xyxy → NMS → top-left-xywh | Internal conversion |

All conversion functions must be named explicitly:
- `xywh_center_to_xyxy(cx, cy, w, h)` → `(x1, y1, x2, y2)`
- `xyxy_to_xywh_top_left(x1, y1, x2, y2)` → `(x, y, w, h)`
- No ambiguous `xywh_to_xyxy` naming.

---

## 10. PC vs RK3588 Task Split

### PC-Side Tasks (all on RTX 4090 / WSL)

| Task | Script/Tool | Output |
|---|---|---|
| Data conversion | `mvtec_mask_to_yolo.py` | YOLO label files |
| Data split | `split_mvtec_localization.py` | train/val txt files |
| Label QA visualization | `visualize_yolo_labels.py` | 50+ QA images |
| YOLOv8n training | `yolo detect train` (ultralytics) | `best.pt`, `metrics.json` |
| PC validation metrics | `eval_yolo_localization.py` | mAP, per-class AP, confusion matrix |
| ONNX export | `yolo export format=onnx` | `yolov8n_phase10.onnx` |
| RKNN conversion | `convert_yolo_rknn.py` (new) | `yolov8n_phase10.rknn` |
| ONNX vs RKNN comparison | `compare_onnx_rknn.py` | Per-class AP delta report |
| Backend/frontend schema | Direct edits | v1.3 contract |
| Contract tests | `pytest backend/tests/contract/` | All green |
| Demo snapshot generation | `phase10_pc_predictions.json` | Static demo data |

### RK3588-Side Tasks (on Orange Pi 5 Plus 16GB)

| Task | Tool | Verification |
|---|---|---|
| RKNN smoke test | `edge_pipeline --config config_phase10_yolo.yaml` | No crash, detections produced |
| Localizer latency measurement | Trace events | <100ms target |
| 30-min soak test | Continuous run | 0 crashes, 0 HTTP 400 |
| Bbox validity check | Log all bboxes | All pass `x+w<=1`, `y+h<=1` |
| End-to-end pipeline | Full T1→T2→T3→T4 | Uploads succeed, data in backend |
| ONNX/RKNN result consistency | Compare on 20 images | Per-class delta explainable |

### Handoff Protocol

1. PC produces `yolov8n_phase10.rknn` + `phase10_classes.yaml` + calibration set.
2. SCP to RK3588: `scp models/yolov8n_phase10.rknn orangepi@192.168.137.66:/home/orangepi/models/`
3. C++ `localizer_worker.cpp` loads RKNN, runs inference, outputs `VlmReport` with YOLO fields.
4. Backend accepts v1.3 payload, frontend displays source-aware overlay.

---

## 11. Acceptance Criteria

### Must-Pass (v1 release gate)

| # | Criterion | Verification |
|---|---|---|
| 1 | **No HTTP 400 from bbox validation** | 30-min soak test on RK3588: `upload_fail_400 == 0` |
| 2 | **`defect_type` is YOLO class, not `"anomaly"`** | Log analysis: >90% of reports have `defect_type` from class map |
| 3 | **Per-class AP reported for all 12 classes** | `eval_yolo_localization.py` output table |
| 4 | **mAP@0.5 >= 0.55 overall** | PC validation metrics |
| 5 | **Frontend shows "Localizer detection" label** | Visual inspection of overlay tooltip |
| 6 | **Frontend shows Phase 10 caveat** | CaveatBanner visible on dashboard |
| 7 | **Contract tests all green** | `pytest backend/tests/contract/ -v` |
| 8 | **`npm run build` passes** | Static export succeeds |
| 9 | **API contract v1.3 documented** | `docs/API_CONTRACT.md` updated |
| 10 | **Supervised POC caveat in README** | README section added |

### Should-Pass (strong recommendation)

| # | Criterion | Verification |
|---|---|---|
| 11 | Per-class AP >= 0.40 for each class | Per-class table |
| 12 | ONNX→RKNN mAP delta < 10% | `compare_onnx_rknn.py` report |
| 13 | Localizer latency < 100ms on RK3588 | Trace event `yolo_localizer` |
| 14 | 80%+ visual QA: bbox covers defect, not whole object | Manual inspection of 50 images |
| 15 | `metal_nut/flip` labeled as "object-level anomaly" | Frontend shows appropriate label |

---

## 12. Risks and Rollback

### Risk Matrix

| Risk | Impact | Likelihood | Mitigation | Rollback |
|---|---|---|---|---|
| YOLOv8n mAP@0.5 < 0.55 | Demo looks bad | Medium | Multi-scale training, copy-paste aug, increase epochs | Switch to YOLOv8s (~28 FPS on RK3588, still <40ms) |
| `cable/bent_wire` AP very low (7 samples) | 1 class fails | High | Accept low AP, document it; or merge into `defect_family` | Drop `bent_wire` class, retrain 11-class |
| RKNN INT8 AP delta > 10% | On-board accuracy bad | Medium | Calibration set tuning, per-channel quant | Ship FP16/no-quant (~40ms, acceptable) |
| `metal_nut/flip` bbox looks like whole object | Demo confusing | High | Label as "object-level pose anomaly", separate report section | Exclude from main metrics, show with caveat |
| API v1.3 backward compat breaks old frontend | Dashboard white screen | Low | `pipeline_ms` accepts both old/new keys | Revert schema changes, use `fastsam` field as compat hack |
| C++ `localizer_worker.cpp` timeline slips | Can't demo on RK3588 | Medium | PC-side Python prototype generates demo snapshot first | Document as "PC prototype, C++ in progress" in README |
| VLM template observation quality poor | Description meaningless | Low | Template is simple string, no VLM needed | Template works as-is for v1 |

### Rollback Procedure

1. **If YOLO training fails:** Keep Phase 9 pipeline unchanged. Phase 10 data scripts and docs still valuable for future.
2. **If RKNN conversion fails:** Ship PC ONNX + Python inference. Generate static demo snapshot.
3. **If C++ integration fails:** Generate snapshot from PC Python. Frontend loads snapshot, shows improved overlay.
4. **If API v1.3 breaks:** Revert to v1.2 schema. Map YOLO fields into existing `defect_type`/`bboxes`/`confidence` fields (same values, just different source). Add `localization_source` to `description` field as compat hack.

### Branch Strategy

- All work on `phase10/localization-refactor-v1`.
- Merge to `main` only after acceptance criteria 1-10 pass.
- Phase 9 `real_run_latest/` snapshot preserved — not overwritten.
