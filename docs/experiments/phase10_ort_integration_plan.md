# Phase 10 v1 — ORT Fallback Edge Demo Integration Plan

## Status: PLAN — pending review before implementation

## Goal

Integrate the validated ONNX Runtime CPU fallback as the interim RK3588 demo
path. This replaces FastSAM (BLOCKED RKNN) and VLM (template-only) at T3 with
a single YOLOv8n ORT localizer that emits correct v1.3 fields.

## Constraints

- No RKNN localizer_worker (RKNN BLOCKED)
- No RKNN threshold tuning
- No INT8 as main path
- No YOLOv8s retraining
- FastSAM remains in codebase but disabled by default
- VLM remains template-only / not called
- C++ pipeline thread model (T1-T4) unchanged

## Architecture: Where ORT Sits

```
T1 CaptureWorker → Q1(4) → T2 EadWorker → Q2(2) → T3* → Q3(4) → T4 UploadWorker
                                     ↓
                            ┌──────────────────┐
                            │  T3: Localizer    │
                            │  Worker (ORT)     │
                            │                   │
                            │  1. Preprocess    │
                            │     (letterbox)   │
                            │  2. ORT inference │
                            │     (YOLOv8n)     │
                            │  3. Decode + NMS  │
                            │  4. Class map     │
                            │  5. VlmReport     │
                            └──────────────────┘
```

T3 becomes `LocalizerWorker` (new file). FastSamWorker stays in codebase but
is not instantiated when `localizer_backend: "ort"` in config.

## Implementation Strategy: Python Subprocess

Use `smoke_test_ort.py` as the inference engine via subprocess, not C++ ORT
linking. Rationale:

| Approach | Pros | Cons |
|----------|------|------|
| **Python subprocess** | Already validated, no C++ rebuild, trivial deployment | ~10ms IPC overhead |
| C++ ORT API | No IPC overhead | Requires libonnxruntime.so link, C++ rebuild, more complex debugging |
| Python HTTP server | Clean separation | Adds a daemon process, port management |

**Chosen: Python subprocess.** The ~10ms IPC overhead is negligible vs 200ms
inference. The validated `smoke_test_ort.py` logic is reused directly.

### Subprocess Protocol

`scripts/phase10/ort_localizer.py` (new, based on `smoke_test_ort.py`):

```
Input:  CLI args + stdin image path (one per line)
Output: stdout JSON lines (one result per image)

Each output line:
{
  "image_path": "/path/to/image.png",
  "defect_type": "bent",
  "confidence": 0.923,
  "bboxes": [{"x": 0.8757, "y": 0.5328, "w": 0.1528, "h": 0.1613}],
  "class_id": 0,
  "class_name": "metal_nut/bent",
  "preprocess_ms": 44.0,
  "inference_ms": 155.8,
  "postprocess_ms": 1.3,
  "total_ms": 201.2,
  "ok": true,
  "error": null
}
```

The C++ `LocalizerWorker` spawns the process once, writes image paths to stdin,
reads JSON from stdout. Model loads once at startup.

### Frame Handoff: Temp Image Files

The Python subprocess receives image file paths over stdin. The C++ worker
writes each frame to a temp file before sending the path.

**image_loop mode:** CaptureFrame already has `image_path` pointing to a real
file on disk. No temp file needed — send the path directly.

**V4L2 mode (future):** Raw frame bytes must be written to a temp JPEG before
sending to Python. This is deferred; v1 demo uses image_loop only.

**Temp dir:** `/tmp/edge_localizer/` (created at worker startup)
- Each temp file: `{frame_id}_{timestamp_us}.jpg`
- Cleanup: delete immediately after Python returns the result for that frame
- Bounded: max 1 file exists at a time (sequential: write → send → read → delete)
- On worker shutdown: purge all remaining temp files
- No unbounded disk growth: cleanup is synchronous, not deferred

**Timeout:** 5 seconds per frame. If Python does not produce a JSON line within
5s of receiving the image path, the worker kills the subprocess, logs the error,
emits a fallback VlmReport, and restarts the subprocess.

**Error fallback:** On any failure (timeout, parse error, subprocess crash),
LocalizerWorker emits a fallback VlmReport:
- `defect_type: "anomaly"`
- `confidence: 0.0`
- `bboxes: [{0.3, 0.3, 0.4, 0.4}]` (center placeholder)
- `localization_source: "ort_fallback"`
- `label_source: "template"`

## v1.3 Field Emission

### VlmReport Changes (`edge/include/edge/common/types.hpp`)

```cpp
struct VlmReport {
  // ... existing fields ...

  // v1.3 source tracking
  std::string localization_source;  // "ort_yolov8n_cpu" or "yolov8n_detect_rknn"
  std::string label_source;         // "yolo_class_head"
  std::string observation_source;   // "template"

  // v1.3 pipeline_ms — add localizer, keep old keys for compat
  struct PipelineMs {
    float efficientad{0.0f};
    float fastsam{0.0f};       // 0.0 when disabled
    float qwen3vl{0.0f};       // 0.0 when disabled
    float localizer{0.0f};     // NEW: ORT inference time
    float upload{0.0f};        // NEW: T4 upload time
  } pipeline_ms;
};
```

### upload_worker Changes (`edge/src/upload/upload_worker.cpp`)

`build_meta_json()` additions:
1. Emit `pipeline_ms.localizer` and `pipeline_ms.upload`
2. Emit `localization_source`, `label_source`, `observation_source` when non-empty
3. Keep `pipeline_ms.fastsam` and `pipeline_ms.qwen3vl` (set to 0.0) for backward compat
4. Keep `schema_version` as `"v1"`; emit v1.3 optional fields alongside it

### Config Changes (`edge/config.yaml`)

```yaml
# ── Localizer (Phase 10) ───────────────────────────
localizer_backend: "ort"         # "ort" | "rknn" | "disabled"
localizer_model_path: /home/orangepi/phase10/models/yolov8n_phase10/yolov8n_metal_nut_cable_best.onnx
localizer_classes_path: /home/orangepi/phase10/configs/phase10_classes.yaml
localizer_conf_thresh: 0.25
localizer_iou_thresh: 0.45
localizer_script_path: /home/orangepi/phase10/scripts/phase10/ort_localizer.py
localizer_img_size: 640

# FastSAM disabled when localizer is active
fastsam_enabled: false           # NEW: explicit disable toggle
```

## How FastSAM Remains Disabled

- `fastsam_enabled: false` in config → `FastSamWorker` is not instantiated
- When `localizer_backend: "ort"` → `LocalizerWorker` is instantiated instead
- FastSamWorker code stays in repo (not deleted)
- `main.cpp` reads config to decide which T3 worker to launch:

```cpp
if (cfg.localizer_backend == "ort") {
  LocalizerWorker t3(cfg, q2, q3, metrics);
  // ...
} else if (cfg.localizer_backend == "rknn") {
  // Future: RKNN localizer (blocked)
} else {
  FastSamWorker t3(cfg, q2, q3, metrics);  // legacy path
}
```

## How VLM Remains Template-Only

- LocalizerWorker does NOT call Qwen3VLRunner
- `observation_source: "template"` (hardcoded in LocalizerWorker)
- VLM fields in VlmReport are set to defaults:
  - `defect_type` = YOLO class head output (e.g. "bent", "scratch")
  - `severity` = "medium" (template default)
  - `vlm_metrics.json_parse_ok` = true (no VLM to fail)
  - `vlm_metrics.ttft_ms` / `decode_tps` / etc. = 0
- Qwen3VLRunner stays in codebase, not instantiated

## Defect Type Mapping

YOLOv8n class head outputs class_id (0-11). Map to defect_type via
`phase10_classes.yaml`:

| class_id | class_name | defect_type |
|----------|-----------|-------------|
| 0 | metal_nut/bent | bent |
| 1 | metal_nut/color | color |
| 2 | metal_nut/flip | flip |
| 3 | metal_nut/scratch | scratch |
| 4 | cable/bent_wire | bent_wire |
| 5 | cable/cable_swap | cable_swap |
| 6 | cable/combined | combined |
| 7 | cable/cut_inner_insulation | cut_inner_insulation |
| 8 | cable/cut_outer_insulation | cut_outer_insulation |
| 9 | cable/missing_cable | missing_cable |
| 10 | cable/missing_wire | missing_wire |
| 11 | cable/poke_insulation | poke_insulation |

The `defect_type` is the part after `/` in the class name. The `category` is
the part before `/`. Both are emitted in the VlmReport.

## Files to Create/Modify

### New Files

| # | File | Purpose |
|---|------|---------|
| 1 | `scripts/phase10/ort_localizer.py` | Python subprocess inference engine (based on smoke_test_ort.py) |
| 2 | `edge/src/pipeline/localizer_worker.hpp` | C++ T3 worker header |
| 3 | `edge/src/pipeline/localizer_worker.cpp` | C++ T3 worker impl (spawns Python, parses JSON) |
| 4 | `docs/experiments/phase10_ort_integration_plan.md` | This document |

### Modified Files

| # | File | Change |
|---|------|--------|
| 1 | `edge/include/edge/common/types.hpp` | Add v1.3 fields to VlmReport |
| 2 | `edge/src/upload/upload_worker.cpp` | Emit v1.3 fields in build_meta_json() |
| 3 | `edge/src/main.cpp` | Config-driven T3 worker selection |
| 4 | `edge/include/edge/common/config.hpp` | Add localizer_* config keys |
| 5 | `edge/src/common/config_loader.cpp` | Parse localizer_* keys from YAML |
| 6 | `edge/config.yaml` | Add localizer section, fastsam_enabled toggle |
| 7 | `edge/CMakeLists.txt` | Add localizer_worker.cpp to build |

## Acceptance Tests (Required Before Merge)

### 1. Python Subprocess Smoke Test

```bash
# On RK3588:
echo "/path/to/metal_nut_bent_000.png" | python3 ort_localizer.py \
  --model yolov8n_metal_nut_cable_best.onnx \
  --classes phase10_classes.yaml \
  --conf 0.25
# Expected: JSON with defect_type="bent", confidence>=0.9, valid bbox
```

### 2. C++ Integration Smoke Test

```bash
# On RK3588 with localizer_backend: "ort":
./edge_pipeline --config config.yaml 2>&1 | head -100
# Expected:
#   [T3] LocalizerWorker started | backend=ort
#   [T3] frame N | cat=metal_nut | defect_type=bent | conf=0.923
#   [T4] meta JSON contains "localizer" in pipeline_ms
#   [T4] meta JSON contains "localization_source":"ort_yolov8n_cpu"
```

### 3. API Contract Validation

```bash
# Run existing contract tests:
pytest backend/tests/contract/ -v
# All 83 tests must pass (v1.3 backward compat)

# Verify v1.3 fields in DB:
curl http://localhost:8000/api/defects?limit=5 | jq '.items[0] | {localization_source, label_source, observation_source, pipeline_ms}'
```

### 4. Frontend Smoke Test

- Dashboard loads without errors
- Defect table shows new entries with correct defect_type
- KPI cards update
- Detail drawer shows v1.3 source fields (if exposed)
- Trace timeline shows "localizer" stage

### 5. 30-Minute Soak Test

```bash
# On RK3588, run continuous inference for 30 minutes:
./edge_pipeline --config config.yaml 2>&1 | tee /tmp/soak_30min.log

# After 30 min, verify:
#   - No crashes / OOM / segfaults
#   - RSS stable (no leak)
#   - upload_ok count increasing
#   - fallback_count = 0 (no emergency bboxes)
#   - pipeline_ms.localizer avg ~200ms (±50ms)
```

### 6. Performance Regression Check

Compare against baseline (FastSamWorker):

| Metric | FastSamWorker (baseline) | LocalizerWorker (ORT) | Gate |
|--------|-------------------------|----------------------|------|
| T3 total ms | ~137ms (RKNN) | ~200ms (CPU) | < 500ms |
| Bbox correctness | N/A (RKNN BLOCKED) | PASS (PyTorch ref) | class match |
| Fallback rate | varies | 0% | < 5% |
| RSS | ~3.3GB (VLM loaded) | ~500MB (no VLM) | < 2GB |

## Deployment Checklist

1. Copy `ort_localizer.py` to RK3588 at config path
2. Copy ONNX model to RK3588 at config path
3. Copy `phase10_classes.yaml` to RK3588 at config path
4. Verify `onnxruntime` installed on RK3588 (`pip3 show onnxruntime`)
5. Update `edge/config.yaml` with `localizer_backend: "ort"`
6. Cross-compile `edge_pipeline` with new localizer_worker
7. Deploy and run smoke test
8. Run 30-min soak test
9. Verify API contract (pytest)

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Python subprocess crash | T3 hangs | Timeout on stdout read (5s), restart process |
| ORT OOM on 16GB board | Pipeline dies | RSS ~500MB, plenty of headroom |
| JSON parse error from Python | T3 fallback | Parse error → emergency bbox fallback |
| Slow subprocess startup | First-frame latency | Pre-warm: send one dummy image at init |
| Classes YAML mismatch | Wrong defect_type | Validate YAML at startup, fail fast |

## What This Is NOT

- This is a **CPU fallback**, not NPU/RKNN deployment
- RKNN remains the target path; this is interim for demo
- This does NOT replace the RKNN issue investigation
- Performance is ~1.5x slower than RKNN NPU but correct
- VLM is not called; severity is template-only
- Only metal_nut + cable (2 classes, 12 defect types) are supported
  by the trained YOLOv8n model. Other categories will get "anomaly" fallback.

## References

- `docs/experiments/phase10_onnxruntime_fallback_plan.md` — ORT validation results
- `docs/experiments/phase10_rknn_fp16_diagnostic.md` — RKNN BLOCKED evidence
- `docs/API_CONTRACT.md` — v1.3 field definitions
- `scripts/phase10/smoke_test_ort.py` — validated ORT inference logic
- `edge/src/pipeline/fastsam_worker.cpp` — current T3 (to be replaced at runtime)
- `edge/src/upload/upload_worker.cpp` — T4 JSON builder (to be extended)
