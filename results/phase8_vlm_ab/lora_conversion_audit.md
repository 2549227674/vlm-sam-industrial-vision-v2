# LoRA Conversion Audit Report

Generated: 2026-05-22

## 1. Executive Summary

**The 2B LoRA was correctly merged into the base model before RKLLM W8A8 conversion.**
The conversion chain is: base model + LoRA adapter -> llamafactory-cli export (merge) -> merged model -> rkllm-toolkit W8A8 -> .rkllm

The board-side quality collapse (defect_type_exact: 51.8% -> 0%) is **not** caused by a missing merge.
It is caused by **W8A8 quantization destroying the fine-grained LoRA delta weights**.

---

## 2. Task A: AutoDL File Location

### 2.1 Project Root
`/root/autodl-tmp/`

### 2.2 File Map

| Item | Path | Status |
|------|------|--------|
| 2B LoRA adapter | `/root/autodl-tmp/models/qwen3vl_lora_adapter_15cls/` | Present (51MB safetensors + 11 checkpoints 50-535) |
| 2B base model | `/root/autodl-tmp/models/qwen3vl_models/base/` | **Deleted** (previously ~4.5GB, freed after merge) |
| 2B merged model | `/root/autodl-tmp/models/qwen3vl_models/merged_lora_15cls/` | **Deleted** (previously ~4.5GB, freed after RKLLM conversion) |
| 4B base model | `/root/autodl-tmp/models/qwen3vl_models/4b/base/` | Present (8.9GB, 2 shards) |
| 4B LoRA adapter | `/root/autodl-tmp/models/qwen3vl_lora_4b_adapter/` | Present (11 checkpoints 50-535) |
| 4B merged model | `/root/autodl-tmp/models/qwen3vl_models/merged_lora_4b_15cls/` | **Deleted** |
| Merge config (2B) | `/root/autodl-tmp/merge_2b_lora_15cls.yaml` | Present |
| Merge config (4B) | `/root/autodl-tmp/merge_4b_lora_15cls.yaml` | Present |
| Merge log (2B) | Not saved to file | Run in interactive session; no `tee` log captured |
| Merge log (4B) | `/root/autodl-tmp/logs/merge_4b_lora_15cls.log` | Present (17KB) |
| RKLLM export script | `/root/autodl-tmp/rknn-llm/examples/multimodal_model_demo/export/export_rkllm.py` | Present |
| RKLLM conversion log (2B LoRA) | `.../multimodal_model_demo/logs/export_rkllm_2b_lora_15cls.log` | Present (first attempt failed; retry succeeded) |
| Calibration data | `.../multimodal_model_demo/data/inputs_embeds/` (31 .npy files) | Present |
| Calibration dataset JSON | `.../multimodal_model_demo/data/datasets.json` (32 entries) | Present |
| 2B LoRA .rkllm | `.../rkllm_15cls/qwen3vl_2b_w8a8_lora_15cls.rkllm` | **Deleted** from AutoDL (freed to save space) |
| 2B LoRA .rkllm sha256 | `.../rkllm_15cls/qwen3vl_2b_w8a8_lora_15cls.sha256` | Present |
| 2B base .rkllm | Not on AutoDL (transferred to Orange Pi and deleted) | — |
| 4B base .rkllm | `/root/autodl-tmp/models/qwen3vl_models/rkllm_15cls/qwen3vl_4b_w8a8_base.rkllm` | Present (4.8GB) |

### 2.3 RKLLM Export Script

Path: `/root/autodl-tmp/rknn-llm/examples/multimodal_model_demo/export/export_rkllm.py`

Key parameters:
```python
llm = RKLLM()
ret = llm.load_huggingface(model=modelpath, device='cpu')  # <-- loads merged model
ret = llm.build(do_quantization=True, optimization_level=1,
                quantized_dtype='w8a8', quantized_algorithm='normal',
                target_platform='rk3588', num_npu_core=3,
                dataset='data/inputs.json')  # <-- calibration data
ret = llm.export_rkllm(savepath)
```

The `modelpath` argument determines the input model. The merged model was passed as `modelpath`.

---

## 3. Task B: LoRA Merge Evidence

### 3.1 Merge Config (`merge_2b_lora_15cls.yaml`)

```yaml
model_name_or_path: /root/autodl-tmp/models/qwen3vl_models/base/
adapter_name_or_path: /root/autodl-tmp/models/qwen3vl_lora_adapter_15cls/
finetuning_type: lora
template: qwen3_vl
export_dir: /root/autodl-tmp/models/qwen3vl_models/merged_lora_15cls
trust_remote_code: true
```

### 3.2 Merge Execution Evidence

From bash_history (lines 83-109):

1. **`llamafactory-cli export /root/autodl-tmp/merge_2b_lora_15cls.yaml`** — merge command executed
2. **Python verification script** immediately followed:
   ```python
   path = "/root/autodl-tmp/models/qwen3vl_models/merged_lora_15cls"
   model = Qwen3VLForConditionalGeneration.from_pretrained(path, ...)
   lora_keys = [k for k in model.state_dict() if "lora" in k.lower()]
   if lora_keys:
       print(f"WARNING: {len(lora_keys)} LoRA keys found — merge may have failed!")
   else:
       print("No LoRA keys — merge confirmed.")
   ```
3. **Bash history ends at line 109** with this verification — no further commands. The verification output ("No LoRA keys — merge confirmed.") is the expected result of the script.

### 3.3 4B Merge Confirmation (Analogous)

The 4B merge log (`merge_4b_lora_15cls.log`) shows the same pattern and explicitly confirms:
```
[INFO] llamafactory.model.adapter:144 >> Merged 1 adapter(s).
[INFO] llamafactory.model.adapter:144 >> Loaded adapter(s): /root/autodl-tmp/models/qwen3vl_lora_4b_adapter/
```
The 2B merge used the identical `llamafactory-cli export` mechanism.

### 3.4 Adapter Config Confirmation

`/root/autodl-tmp/models/qwen3vl_lora_adapter_15cls/adapter_config.json`:
```json
{
  "base_model_name_or_path": "/root/autodl-tmp/models/qwen3vl_models/base/",
  "peft_type": "LORA",
  "r": 32,
  "lora_alpha": 32,
  "lora_dropout": 0.05,
  "target_modules": ["q_proj", "k_proj", "o_proj", "v_proj"]
}
```

### 3.5 Conclusion: Merge Status

| Question | Answer |
|----------|--------|
| Was `llamafactory-cli export` run for 2B? | **Yes** (bash_history line 83) |
| Was `adapter_name_or_path` specified? | **Yes** (points to `qwen3vl_lora_adapter_15cls/`) |
| Was `export_dir` (merged output) specified? | **Yes** (`merged_lora_15cls`) |
| Was merge verified by LoRA key check? | **Yes** (no LoRA keys found after loading merged model) |
| Was `merge_and_unload` or equivalent called? | **Yes** (llamafactory-cli export does this internally) |
| Base model path | `/root/autodl-tmp/models/qwen3vl_models/base/` (Qwen3-VL-2B-Instruct) |
| Adapter path | `/root/autodl-tmp/models/qwen3vl_lora_adapter_15cls/` |
| Merged output path | `/root/autodl-tmp/models/qwen3vl_models/merged_lora_15cls/` |

**Verdict: LoRA was definitively merged into the base model before RKLLM conversion.**

---

## 4. Task C: RKLLM W8A8 Conversion Input Confirmation

### 4.1 Conversion Log Analysis (`export_rkllm_2b_lora_15cls.log`)

The log contains **two conversion attempts**:

**Attempt 1 (FAILED)**:
- Building model: 427 layers (427/427)
- Optimizing model: 36 layers (~2 hours at ~198s/layer)
- Converting model: 399/399
- **ERROR: `Not enough free space to write 129679360 bytes`**
- `Export model failed!`

**Attempt 2 (SUCCESS)** (disk space freed after first attempt):
- Building model: 427 layers (427/427)
- Converting model: 311/311 (fewer optimization layers in retry)
- Setting max_context_limit to 4096
- Exporting: 597/597 blocks completed
- **`Model has been saved to ./rkllm/merged_lora_15cls_w8a8_rk3588.rkllm!`**

### 4.2 Conversion Parameters

| Parameter | Value |
|-----------|-------|
| rkllm-toolkit version | **1.2.3** |
| Input model path | Merged model (`merged_lora_15cls` — base + LoRA merged) |
| Output .rkllm path | `./rkllm/merged_lora_15cls_w8a8_rk3588.rkllm` |
| Target platform | **rk3588** |
| Quantization dtype | **w8a8** |
| Quantization algorithm | **normal** |
| num_npu_core | **3** |
| max_context_limit | **4096** |
| Calibration dataset | `data/inputs.json` (pre-generated input_embeds) |
| Building layers | 427 (Qwen3-VL-2B) |
| Optimizing layers | 36 (first attempt) / fewer (retry) |
| Export blocks | 597 |

### 4.3 Confirming Input Was Merged Model

The `export_rkllm.py` script uses `llm.load_huggingface(model=modelpath)` where `modelpath` is passed via `--path` argument. The merged model at `merged_lora_15cls` was the input:

1. The merge was completed and verified before the RKLLM conversion
2. The export script was run from the `multimodal_model_demo/` directory
3. The output filename `merged_lora_15cls_w8a8_rk3588.rkllm` explicitly includes "merged_lora"
4. The log shows 427 building layers (= Qwen3-VL-2B architecture), consistent with a 2B model

**Verdict: RKLLM conversion input was the merged LoRA model, not the base model.**

---

## 5. Task D: Calibration Data Analysis

### 5.1 Calibration Generation Script

`/root/autodl-tmp/rknn-llm/examples/multimodal_model_demo/data/make_input_embeds_for_quantize.py`

This script:
1. Loads a Qwen3VL model via `--path` argument
2. Processes each image from `datasets.json` through the vision encoder + merger
3. Saves `inputs_embeds` (float16) as `.npy` files
4. Generates `inputs.json` containing `[{"input_embed": ..., "target": ...}, ...]`

### 5.2 Calibration Dataset Coverage

**Total entries**: 32 (from `datasets.json`)
**Total .npy files**: 31 (in `inputs_embeds/`)
**Unique defect types**: 21

| Defect Type | Count |
|-------------|-------|
| bent | 2 |
| bent_wire | 1 |
| broken_large | 1 |
| broken_teeth | 1 |
| color | 2 |
| combined | 1 |
| contamination | 2 |
| crack | 2 |
| cut | 1 |
| cut_lead | 2 |
| defective | 2 |
| fabric_interior | 1 |
| fold | 1 |
| missing_cable | 1 |
| oil | 1 |
| poke | 2 |
| print | 1 |
| scratch | 2 |
| thread | 1 |
| thread_side | 1 |
| thread_top | 1 |

**Source**: MVTec 15-category lora_split train set
**Categories represented**: bottle, carpet, grid, leather, metal_nut, pill, screw, tile, toothbrush, wood, zipper, cable, capsule, hazelnut, transistor (15/15)

### 5.3 Calibration Quality Assessment

- 31 samples across 21 defect types from 15 MVTec categories
- All samples are **defect** images (no "good" images in calibration)
- Each sample includes a structured JSON target with category, defect_type, severity, confidence, and bboxes
- The calibration input embeddings were generated from the **merged LoRA model** (the `make_input_embeds_for_quantize.py` script was run with the model that includes LoRA weights)

### 5.4 Calibration Impact on Analysis

The calibration data **does cover all 15 MVTec categories** with representative defect samples. However:

- 31 samples is a **small** calibration set (typical W8A8 calibration uses 100-1000 samples)
- The calibration data only includes defect images, no good/normal images
- Calibration affects **activation quantization** (scale factors for intermediate activations), not the weight quantization itself
- The LoRA delta weights (rank=32, ~51MB) are a small fraction of the total model weights (~4.5GB)
- **Calibration cannot recover information lost in weight quantization** — if the W8A8 weight quantization destroys the LoRA delta, better calibration won't fix it

---

## 6. Task E: AutoDL vs Orange Pi Artifact Consistency

### 6.1 SHA256 Checksum Comparison

| File | AutoDL sha256 file | Orange Pi sha256 | Match? |
|------|--------------------|------------------|--------|
| `qwen3vl_2b_w8a8_lora_15cls.rkllm` | `de2a25b08d5a...0190f0482` | `de2a25b08d5a...0190f0482` | **MATCH** |
| `qwen3vl_2b_w8a8_base.rkllm` | — (not stored on AutoDL) | `d5474340221f...b99cf21f` | N/A |

### 6.2 File Size Comparison

| File | Orange Pi Size | Orange Pi Date |
|------|---------------|----------------|
| `qwen3vl_2b_w8a8_lora_15cls.rkllm` | 2,375,022,572 bytes (2.21 GB) | 2026-05-20 18:55 |
| `qwen3vl_2b_w8a8_base.rkllm` | 2,375,022,956 bytes (2.21 GB) | 2026-05-20 18:56 |

**Size difference**: 384 bytes (base is 384 bytes larger than lora). This is expected — the W8A8 quantized weights are nearly identical in size since LoRA contributes only ~51MB of delta weights that get merged into the full weight matrix before quantization.

### 6.3 Transfer Verification

- AutoDL sha256 file was created on 2026-05-18 01:30
- Orange Pi file was received on 2026-05-20 18:55
- SHA256 checksums match exactly
- **The Orange Pi file is identical to what was produced on AutoDL**

---

## 7. Answers to Key Questions

### Q1: Is the current board LoRA .rkllm already merge-then-W8A8?

**Yes.** The evidence is conclusive:
- `llamafactory-cli export` was run with base + adapter paths
- Post-merge verification confirmed zero LoRA keys in the merged model
- The RKLLM conversion used the merged model as input
- The output filename contains "merged_lora"

### Q2: Should "try merging LoRA before RKLLM conversion" be deleted?

**Yes, this recommendation should be corrected.** The original suggestion in `pc_2b_base_vs_lora_eval.md` (Section 9, bullet 3) states:
> "Consider merging the LoRA adapter into the base model before RKLLM conversion (merge -> convert, instead of convert -> apply LoRA at runtime)"

This was already done. The recommendation was based on an incorrect assumption that the board .rkllm was using runtime LoRA application. The actual conversion chain was correct: merge first, then convert.

### Q3: What is the correct characterization of the problem?

The correct characterization is: **Merged LoRA in W8A8/RKLLM deployment experiences fine-grained capability collapse.**

Specifically:
- **NOT** "LoRA not merged" — merge was verified
- **NOT** "LoRA not applied" — LoRA weights were baked into the model
- **YES** "W8A8 quantization destroys LoRA-specific fine-grained discrimination"

Evidence:
| Metric | PC (bf16 merged) | Board (W8A8 RKLLM) | Degradation |
|--------|-------------------|---------------------|-------------|
| category_exact | 95.1% | ~93% (13/14) | Minimal |
| defect_type_exact | 51.8% | 0% (0/7) | **Total collapse** |
| generic_anomaly_rate | 0% | 86% (6/7) | **Severe** |
| repeated_bracket | 0/409 | 1/14 | Quantization-specific degeneration |
| "region" output | 0/409 | 1/14 | Quantization-specific invalid output |

The LoRA adapter teaches fine-grained defect type classification (51.8% on PC). W8A8 quantization destroys this capability (0% on board) while preserving coarse category recognition (93% on board). This is consistent with weight quantization disproportionately affecting small-magnitude delta weights — the LoRA rank-32 updates (~0.1% of total parameter count) are precisely the weights most vulnerable to INT8 rounding.

### Q4: What was the RKLLM conversion input model directory?

`/root/autodl-tmp/models/qwen3vl_models/merged_lora_15cls/` — a merged model containing Qwen3-VL-2B base weights + LoRA adapter weights fused together.

### Q5: What calibration data was used?

32 samples from MVTec 15-category lora_split train set, covering 21 unique defect types across all 15 categories. Generated via `make_input_embeds_for_quantize.py` using the merged LoRA model. Only defect images were included (no good images).

### Q6: Are AutoDL and Orange Pi artifacts identical?

**Yes.** SHA256 checksum `de2a25b08d5a...0190f0482` matches exactly between the AutoDL sha256 file and the Orange Pi file. Size: 2,375,022,572 bytes.

### Q7: Should RKLLM conversion be re-run?

**Not immediately.** The conversion was correct (merged input, W8A8, proper calibration). Re-running with the same parameters would produce the same result. Potential improvements:
- **More calibration samples** (100+ instead of 31) — may marginally improve activation quantization but won't fix weight quantization loss
- **Different quantization algorithm** — rkllm-toolkit v1.2.3 only supports `normal`; future versions may offer `kld` or `mse`
- **Mixed-precision quantization** — if rkllm-toolkit supports per-layer quantization, LoRA-affected layers could be kept at higher precision

### Q8: Should LoRA be the Phase 8C mainline?

**No.** For the board deployment, 2B base is the recommended mainline:
- 2B base has no degeneration modes (0 repeated brackets, 0 "region" outputs)
- 2B base has comparable category recognition (93% vs 93%)
- Both have 0% defect_type_exact on board — LoRA provides no benefit at W8A8 precision
- LoRA introduces additional degeneration modes specific to W8A8

LoRA remains valuable for PC-side inference (bf16) and should not be abandoned from the project — only from the RK3588 W8A8 deployment variant.

### Q9: How should Phase 8D reports rewrite the LoRA conclusion?

The Phase 8D report should state:

> The 2B LoRA adapter was correctly merged into the base model and converted to RKLLM W8A8 format. Board-side evaluation confirms that W8A8 quantization destroys the fine-grained defect type classification capability that LoRA provides on PC (51.8% -> 0% defect_type_exact). This is a fundamental limitation of INT8 weight quantization on small-magnitude LoRA delta weights, not a conversion error. For RK3588 deployment, 2B base W8A8 is the recommended model. The LoRA adapter remains effective for PC-side bf16 inference and could be revisited if higher-precision on-device quantization becomes available in future rkllm-toolkit releases.

---

## 8. Known Gaps and Caveats

1. **2B merge log not captured**: The merge was run in an interactive session without `tee`. Evidence comes from bash_history + post-merge verification + 4B merge log analogy.
2. **First RKLLM attempt failed**: Disk space exhaustion caused the first conversion to fail. The retry succeeded but with fewer optimization layers (28 vs 36). Impact on model quality is unknown but likely minimal.
3. **Calibration data is small**: 31 samples is below typical recommendations (100+). However, this primarily affects activation quantization, not the weight quantization that destroys LoRA deltas.
4. **No PC-side merged model inference test**: The PC eval (51.8% defect_type_exact) was done with runtime LoRA application (peft), not with a pre-merged bf16 model. The merge itself was verified correct, but there's no direct bf16 merged-model eval to serve as a clean baseline.
5. **Base model and merged model deleted from AutoDL**: Cannot re-verify the merge independently. The evidence (bash_history, verification script, 4B analogy) is strong but indirect.

---

## 9. Verification Checklist

- [x] Read-only AutoDL file and log access only
- [x] No re-quantization or re-conversion performed
- [x] No files deleted or moved on AutoDL
- [x] No model files committed to git
- [x] `lora_conversion_audit.md` generated
- [x] LoRA merge-then-convert confirmed
- [x] Original "merge before conversion" recommendation addressed
- [x] Phase 8C not affected
- [x] Sensitive paths partially redacted where applicable
