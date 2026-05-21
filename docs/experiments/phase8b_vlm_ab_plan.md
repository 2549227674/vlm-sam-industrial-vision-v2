# Phase 8B: VLM A/B Evaluation Plan

Generated: 2026-05-22

## 0. Prerequisites

Phase 8A series is sealed:
- Phase 8A: RKNN raw score 15-class calibration complete.
- Phase 8A-Fix: 5 score_mode comparison complete.
- Phase 8A-Fix-Fix: config threshold scale consistency and recall@FPR monotonicity fixed.
- Current config: `efficientad_score_mode=raw_score`, all `per_category_threshold` = raw_score good_p95.
- T2 gate is a load shedding gate, not a detection gate.

## 1. Task A: VLM Variant Runtime Audit

### 1.1 Code analysis

From `edge/src/vlm/qwen3vl_runner.cpp` lines 129-160, the `init()` method:

| Variant | Config keys used | Status |
|---------|-----------------|--------|
| 2B base | `vlm_model_path` + `vlm_vision_model_path` | **Working** - used directly |
| 2B LoRA | `vlm_2b_lora_model_path` + `vlm_vision_model_path` | **Working** - validates file existence, fails init if missing |
| 4B base | Falls back to 2B base with WARNING | **NOT implemented** |
| 4B LoRA | Falls back to 2B base with WARNING | **NOT implemented** |

The 4B branch (line 146-152) prints:
```
[VLM] WARNING: 4B variant not yet implemented in this build, falling back to 2B base
```
and then uses `cfg_.vlm_model_path` (2B base) regardless of variant.

### 1.2 Config paths that are never used at runtime

The following config keys exist in `edge/config.yaml` but are **never read by the runtime** for actual model loading:

- `vlm_4b_model_path` (line 98)
- `vlm_4b_vision_model_path` (line 99)
- `vlm_4b_lora_model_path` (line 102)

These are dead config. Setting `vlm_model_size: "4B"` in config.yaml triggers the fallback-to-2B path.

### 1.3 Answers

1. **2B base**: Can run directly. Uses `vlm_model_path` + `vlm_vision_model_path`.
2. **2B LoRA**: Can run directly. Uses `vlm_2b_lora_model_path` + `vlm_vision_model_path`. File existence validated.
3. **4B base**: Falls back to 2B base. NOT a real 4B path.
4. **4B LoRA**: Falls back to 2B base. NOT a real 4B path.
5. **4B config paths**: Never used by runtime. Dead config.
6. **4B benchmark**: **MUST NOT generate 4B benchmark results** — would be measuring 2B base under a different label.

### 1.4 Blocking point

**Cannot do 4-variant board A/B.** Only 2B base and 2B LoRA are real variants. A 4-variant A/B would produce misleading results: the "4B" variants would actually run 2B base weights.

## 2. Task B: Phase 8B Experiment Design

### 2.1 Phase 8B-Board-2B (Orange Pi RKLLM runtime)

**Goal**: Compare 2B base vs 2B LoRA on the board using real RKLLM inference.

**Method**:
- Use `config.debug.yaml` as base (has `pass_all` gate mode).
- For each variant, modify only `vlm_variant` ("base" vs "lora") and `vlm_model_size` ("2B").
- Run edge_pipeline against the fixed sample list (see Task C).
- Each variant is an independent process launch. Never load both simultaneously (16GB RAM constraint: 2B base RSS ~3.3GB, 2B LoRA RSS ~3.3GB).

**Metrics to collect**:
| Metric | Source |
|--------|--------|
| json_parse_ok | T3 VLM JSON extraction success |
| fallback | T3 rule-based fallback triggered |
| output_tokens | RKLLM callback `generate_tokens` |
| prompt_tokens | RKLLM callback `prefill_tokens` |
| TTFT (ms) | RKLLM callback `prefill_time_ms` |
| decode_tps | `generate_tokens / (generate_time_ms / 1000)` |
| pipeline_ms.qwen3vl | T3 total wall-clock |
| RSS (MB) | RKLLM callback `memory_usage_mb` |
| upload_ok | T4 curl success count |

**Config template** (per variant):
```yaml
# Phase 8B-Board-2B: {variant_name}
vlm_variant: "{base|lora}"
vlm_model_size: "2B"
efficientad_gate_mode: pass_all  # bypass T2 threshold gate
image_loop_categories: [subset from fixed_samples.txt]
image_loop_beat_ms: 5000  # generous interval for VLM to finish
```

**Important**:
- Use `pass_all` or direct image list, NOT threshold gate. Reason: threshold gate drops ~60% of frames (AUROC < 0.80), which biases the sample toward high-anomaly images and makes the VLM quality comparison unfair.
- Each variant must process the same set of images.
- Record per-frame results in the upload JSON (backend already stores them).

### 2.2 Phase 8B-PC (PC-side transformers)

**Goal**: Compare output quality of all 4 model variants using PC transformers (GPU).

**Method**:
- Use `scripts/eval_ab_test.py` (already supports `--model-size 2B` and `--model-size 4B`).
- Run on the LoRA eval split (`datasets/lora_split/eval/`).
- Measures JSON quality metrics, NOT latency/throughput.

**Metrics**:
| Metric | Meaning |
|--------|---------|
| json_parse_ok | Valid JSON with all required keys |
| schema_ok | Passes DefectCreate schema constraints |
| category_exact | Predicted category matches ground truth |
| defect_type_exact | Predicted defect_type matches ground truth |
| severity_valid | Severity in {low, medium, high} |
| bbox_iou_at_0_5 | IoU >= 0.5 for at least one predicted bbox |
| prompt_tokens | Number of input tokens |
| output_tokens | Number of generated tokens |

**What PC results represent**: Model output quality only. NOT RK3588 performance. GPU latency is irrelevant to deployment.

**Variants**:
| Variant | Model | Prompt |
|---------|-------|--------|
| 2B_base | Qwen3-VL-2B base | Engineered (~300 tokens) |
| 2B_lora | Qwen3-VL-2B LoRA | Minimal (~50 tokens) |
| 4B_base | Qwen3-VL-4B base | Engineered (~300 tokens) |
| 4B_lora | Qwen3-VL-4B LoRA | Minimal (~50 tokens) |

PC can run all 4 variants because it uses transformers (not RKLLM), so 4B models are loadable on GPU.

### 2.3 Phase 8B-4B (Board 4B smoke test)

**Goal**: Validate real 4B path on the board.

**Precondition**: `qwen3vl_runner.cpp` must be modified to implement real 4B path (load `vlm_4b_model_path` + `vlm_4b_vision_model_path` when `vlm_model_size == "4B"`).

**Method**:
- Run 3-5 images only (smoke test).
- Monitor: RSS, TTFT, decode_tps, pipeline_ms.qwen3vl, OOM.
- Expected RSS: ~8.7GB (4B base) or ~8.7GB (4B LoRA). Pipeline total ~11.4GB. Margin ~3.1GB.

**Critical**: Do NOT record fallback-to-2B results as 4B results.

**This phase is BLOCKED until qwen3vl_runner.cpp 4B path is implemented.**

### 2.4 Phase 8C (deferred)

- Starts only after Phase 8B-Board data is available.
- First target: `image_loop_beat_ms` parameter sweep.
- Do NOT simultaneously adjust queue capacity, timeout, or threshold.

## 3. Task C: Fixed Sample List Design

### 3.1 Design rationale

For Phase 8B-Board-2B, we need a small fixed sample list that:
- Covers at least 5 representative categories.
- Includes both good and defect images per category.
- Does NOT depend on T2 threshold gate (which would filter out ~60% of samples).
- Is deterministic (same images each run for reproducibility).

### 3.2 Sample list

7 categories, 2 images each (1 good + 1 defect) = 14 total images.

Selected to cover:
- High AUROC: tile (0.8193), carpet (0.7887)
- Medium AUROC: grid (0.6099), metal_nut (0.6173)
- Low AUROC: zipper (0.4766), pill (0.3682), screw (0.5337)

| # | Category | Label | Defect Type | Image Path |
|---|----------|-------|-------------|------------|
| 1 | tile | good | - | simulator/mvtec/tile/test/good/023.png |
| 2 | tile | defect | crack | simulator/mvtec/tile/test/crack/011.png |
| 3 | carpet | good | - | simulator/mvtec/carpet/test/good/023.png |
| 4 | carpet | defect | color | simulator/mvtec/carpet/test/color/011.png |
| 5 | grid | good | - | simulator/mvtec/grid/test/good/011.png |
| 6 | grid | defect | bent | simulator/mvtec/grid/test/bent/011.png |
| 7 | metal_nut | good | - | simulator/mvtec/metal_nut/test/good/011.png |
| 8 | metal_nut | defect | bent | simulator/mvtec/metal_nut/test/bent/023.png |
| 9 | zipper | good | - | simulator/mvtec/zipper/test/good/023.png |
| 10 | zipper | defect | broken_teeth | simulator/mvtec/zipper/test/broken_teeth/011.png |
| 11 | pill | good | - | simulator/mvtec/pill/test/good/011.png |
| 12 | pill | defect | color | simulator/mvtec/pill/test/color/011.png |
| 13 | screw | good | - | simulator/mvtec/screw/test/good/011.png |
| 14 | screw | defect | scratch_head | simulator/mvtec/screw/test/scratch_head/011.png |

## 4. Task D: Execution Constraints

This round is **audit and plan only**. The following are PROHIBITED:

- Running `edge_pipeline`
- Running 4B models
- Modifying `qwen3vl_runner.cpp`
- Modifying `config.yaml`
- Generating benchmark numbers
- Entering Phase 8C

## 5. Task E: Final Answers

### Q1: Can we do 4-variant board A/B now?

**No.** Only 2 variants (2B base, 2B LoRA) are real. 4B base and 4B LoRA both silently fall back to 2B base in `qwen3vl_runner.cpp:146-152`.

### Q2: What is the blocking point?

`qwen3vl_runner.cpp` has a TODO stub for 4B support (line 147-152). It prints a warning and uses 2B paths regardless. The 4B config keys (`vlm_4b_model_path`, `vlm_4b_vision_model_path`, `vlm_4b_lora_model_path`) exist in `edge/config.yaml` and `config.hpp` but are never read by the runtime.

### Q3: Why can't VLM quality evaluation use threshold gate?

The T2 threshold gate is a load shedding gate with AUROC < 0.80 for 14/15 categories. At `good_p95` thresholds, the gate passes only ~40% of frames, biased toward high-anomaly samples. This would:
- Skew VLM evaluation toward easy-to-detect defects.
- Exclude normal-looking defect images (low anomaly score but real defect).
- Make the comparison between variants unfair if the gate behavior changes with score_mode.

Using `pass_all` ensures all images are evaluated, giving an unbiased quality comparison.

### Q4: How should Phase 8B-Board-2B run?

1. Prepare fixed sample list (14 images, 7 categories).
2. Create `config.phase8b_2b_base.yaml` from `config.debug.yaml`, set `vlm_variant: "base"`, `vlm_model_size: "2B"`, `gate_mode: pass_all`.
3. Create `config.phase8b_2b_lora.yaml`, same but `vlm_variant: "lora"`.
4. Run each variant independently (not simultaneously).
5. Collect per-frame metrics from backend `/api/defects` and T2/T3 stderr logs.
6. Compare: json_parse_ok, fallback, output_tokens, TTFT, decode_tps, RSS, upload_ok.

### Q5: What do PC and Board results represent?

| | PC results | Board results |
|---|-----------|--------------|
| What it measures | Model output quality (JSON schema, defect_type accuracy, severity accuracy) | Runtime performance on RK3588 (TTFT, decode_tps, RSS, pipeline latency) |
| Hardware | NVIDIA GPU (RTX 4090) | RK3588 16GB NPU |
| Models | All 4 variants (2B/4B base/LoRA via transformers) | Only 2B variants (2B base, 2B LoRA via RKLLM) |
| Valid for | Selecting which model variant has best output quality | Measuring real deployment performance |

### Q6: What should Phase 8C wait for?

Phase 8C (beat_ms parameter sweep) should wait for:
1. Phase 8B-Board-2B completion — know the actual VLM latency per variant.
2. Selection of the deployment variant (2B base or 2B LoRA).
3. Understanding of T3 processing time distribution under real load.

Only then can `image_loop_beat_ms` be tuned to match T3 capacity without causing queue drops.
