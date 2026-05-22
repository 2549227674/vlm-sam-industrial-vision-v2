# Phase 8B-PC: 2B Base vs 2B LoRA PC-Side Quality Evaluation

Generated: 2026-05-22

## 1. Test Configuration

| Parameter | Value |
|-----------|-------|
| Hardware | RTX 4060 Laptop (8GB VRAM) |
| Framework | transformers 5.6.0 + peft 0.18.1 |
| Precision | bfloat16 |
| Eval split | datasets/lora_split/eval/ (409 samples, 15 categories, defect only) |
| max_new_tokens | 200 |
| Prompt (base) | Engineered prompt (~300 tokens, Chinese) |
| Prompt (LoRA) | Minimal prompt (~50 tokens, Chinese) |
| do_sample | False (greedy decoding) |

## 2. Overall Results

| Metric | 2B Base | 2B LoRA | Delta |
|--------|---------|---------|-------|
| **json_parse_ok** | 391/409 (95.6%) | 393/409 (96.1%) | +0.5% |
| **schema_ok** | 391/409 (95.6%) | 393/409 (96.1%) | +0.5% |
| **category_exact** | 220/409 (53.8%) | **389/409 (95.1%)** | **+41.3%** |
| **defect_type_exact** | 47/409 (11.5%) | **212/409 (51.8%)** | **+40.3%** |
| severity_valid | 391/409 (95.6%) | 393/409 (96.1%) | +0.5% |
| **bbox_iou_at_0_5** | 5/409 (1.2%) | **195/409 (47.7%)** | **+46.5%** |
| repeated_bracket_count | 0 | 0 | 0 |
| empty_generation_count | 0 | 0 | 0 |
| generic_anomaly_count | 0 | 0 | 0 |
| output_tokens_mean | 119.0 | 109.8 | -9.2 |
| output_tokens_max | 200 | 200 | 0 |
| prompt_tokens_mean | 1156.0 | 958.0 | -198 |
| unique_defect_types | 19 | 59 | +40 |

**LoRA is dramatically superior on PC across all quality metrics.**

## 3. Per-Category defect_type_exact

| Category | 2B Base | 2B LoRA | Delta |
|----------|---------|---------|-------|
| bottle | 0/20 (0%) | 14/20 (70%) | +70% |
| cable | 0/30 (0%) | 6/30 (20%) | +20% |
| capsule | 7/34 (21%) | 19/34 (56%) | +35% |
| carpet | 4/30 (13%) | 21/30 (70%) | +57% |
| grid | 0/20 (0%) | 6/20 (30%) | +30% |
| hazelnut | 7/24 (29%) | 16/24 (67%) | +38% |
| leather | 0/30 (0%) | 21/30 (70%) | +70% |
| metal_nut | 10/29 (34%) | 25/29 (86%) | +52% |
| pill | 8/46 (17%) | 26/46 (57%) | +40% |
| screw | 0/38 (0%) | 13/38 (34%) | +34% |
| tile | 6/28 (21%) | 18/28 (64%) | +43% |
| toothbrush | 0/9 (0%) | 5/9 (56%) | +56% |
| transistor | 0/12 (0%) | 3/12 (25%) | +25% |
| wood | 5/20 (25%) | 9/20 (45%) | +20% |
| zipper | 0/39 (0%) | 10/39 (26%) | +26% |

LoRA outperforms base in ALL 15 categories.

## 4. Per-Category bbox_iou_at_0_5

| Category | 2B Base | 2B LoRA |
|----------|---------|---------|
| bottle | 0/20 | 5/20 (25%) |
| cable | 0/30 | 5/30 (17%) |
| capsule | 0/34 | 10/34 (29%) |
| carpet | 2/30 (7%) | 19/30 (63%) |
| grid | 0/20 | 3/20 (15%) |
| hazelnut | 0/24 | 12/24 (50%) |
| leather | 1/30 (3%) | 20/30 (67%) |
| metal_nut | 0/29 | 21/29 (72%) |
| pill | 1/46 (2%) | 33/46 (72%) |
| screw | 0/38 | 8/38 (21%) |
| tile | 0/28 | 21/28 (75%) |
| toothbrush | 0/9 | 4/9 (44%) |
| transistor | 0/12 | 3/12 (25%) |
| wood | 1/20 (5%) | 15/20 (75%) |
| zipper | 0/39 | 16/39 (41%) |

LoRA outperforms base in ALL 15 categories for bbox accuracy.

## 5. Degeneration Pattern Analysis

### 5.1 Repeated Brackets

| Variant | PC (transformers) | Board (RKLLM W8A8) |
|---------|-------------------|---------------------|
| 2B Base | 0/409 | 0/14 |
| 2B LoRA | **0/409** | **1/14 (grid/bent, 499 tok)** |

**The repeated bracket degeneration is RKLLM/W8A8-specific.** It does NOT occur on PC transformers.

### 5.2 Long Output (>=190 tokens)

| Variant | Count | Max tokens |
|---------|-------|------------|
| 2B Base | 31/409 (7.6%) | 200 |
| 2B LoRA | 15/409 (3.7%) | 200 |

Neither variant hits 499 tokens on PC. The max is 200 (the configured limit).

### 5.3 Predicted Defect Types

**2B Base top predictions:**
- scratch: 232 (57% of all predictions!)
- bent: 60
- crack: 57
- (empty): 18

Base model is heavily biased toward "scratch" regardless of input.

**2B LoRA top predictions:**
- scratch: 35 (8.6%)
- crack: 34
- color: 33
- cut: 25
- contamination: 15
- bent: 13
- hole: 13
- combined: 13
- thread_top: 11
- scratch_head: 11

LoRA produces diverse, category-appropriate defect types.

### 5.4 Grid/Bent (Critical Board Degeneration Case)

| Variant | PC predictions for grid/bent samples |
|---------|--------------------------------------|
| 2B Base | "scratch" (category="metal_nut") for all 4 samples |
| 2B LoRA | "combined", "cut", "squeezed", "bent" (1/4 exact match) |

On PC, LoRA produces reasonable (if imperfect) predictions for grid/bent. No repeated brackets.

### 5.5 "region" Invalid Output

| Variant | PC "region" count | Board "region" count |
|---------|-------------------|---------------------|
| 2B Base | 0/409 | 0/14 |
| 2B LoRA | 0/409 | 1/14 (screw/scratch_head) |

The "region" output is also RKLLM/W8A8-specific.

## 6. PC vs Board Comparison

| Metric | PC LoRA | Board LoRA | Interpretation |
|--------|---------|------------|----------------|
| defect_type_exact | **51.8%** | **0%** | RKLLM destroys fine-grained classification |
| category_exact | **95.1%** | ~93% (13/14) | Category recognition survives quantization |
| repeated_bracket | **0** | **1** (deterministic) | Quantization-induced degeneration |
| "region" output | **0** | **1** | Quantization-induced invalid output |
| generic_anomaly_rate | **0%** | **86%** (6/7 defect) | Quantization collapses to generic output |
| bbox_iou≥0.5 | **47.7%** | N/A (board bbox from FastSAM) | — |

## 7. Answers to Key Questions

### Q1: Does PC LoRA improve defect_type_exact over base?
**Yes, massively.** 51.8% vs 11.5% (+40.3 percentage points). LoRA is strictly superior on PC.

### Q2: Does PC LoRA reduce generic anomaly rate?
**Yes.** Both variants predict 0 "anomaly" on PC. But base predicts "scratch" for 57% of samples (equally generic). LoRA produces 59 unique defect types vs base's 19.

### Q3: Does PC LoRA improve good/none output?
**Cannot evaluate.** The eval split has 0 good samples (409 defect-only). See limitations below.

### Q4: Does PC reproduce grid defect repeated bracket degeneration?
**No.** 0/409 repeated brackets on PC. The degeneration is specific to RKLLM/W8A8 quantization.

### Q5: Does PC produce "region" invalid output?
**No.** 0/409 "region" outputs on PC. This is also RKLLM/W8A8-specific.

### Q6: If PC LoRA has improvement but board does not, does this support "RKLLM/W8A8 quantization loss" hypothesis?
**Yes, strongly.** The data supports this hypothesis:
- PC LoRA: 51.8% defect_type_exact, 0 repeated brackets, 0 "region"
- Board LoRA: 0% defect_type_exact, 1 repeated bracket, 1 "region"
- The LoRA adapter itself is sound. The RKLLM W8A8 quantization destroys the fine-grained discrimination that LoRA provides.

### Q7: If PC LoRA also had no improvement, would it support "training/data/prompt" hypothesis?
**Not applicable.** PC LoRA has massive improvement. The training is effective.

### Q8: Should 2B base still be deployed on board?
**Yes, for now.** On the board, 2B base is more reliable:
- 0 repeated brackets (LoRA has 1)
- 0 "region" outputs (LoRA has 1)
- 92.9% json_parse_ok (vs LoRA's 100% but with degeneration caveats)
- 0% defect_type_exact for both, but base has fewer degeneration modes

### Q9: Should LoRA be retrained, prompt adjusted, or abandoned?
**The LoRA adapter should NOT be abandoned.** It works well on PC (51.8% defect_type_exact). Instead:
1. Investigate why RKLLM W8A8 quantization degrades LoRA-specific weights
2. Consider using a higher-precision RKLLM quantization if available
3. Consider merging the LoRA adapter into the base model before RKLLM conversion (merge → convert, instead of convert → apply LoRA at runtime)
4. If higher-precision quantization is not feasible on RK3588, the LoRA approach may need to be abandoned for board deployment specifically

### Q10: Can we enter Phase 8C with 2B base?
**Yes.** Phase 8C (beat_ms sweep) with 2B base is appropriate. The PC eval confirms that:
1. 2B base has reasonable output quality (53.8% category_exact, 11.5% defect_type_exact)
2. No degeneration modes on PC or board
3. The deployment variant decision is clear: 2B base for board

## 8. Limitations

1. **No good samples in eval split.** Cannot evaluate none_rate or good image handling.
2. **Different prompts.** Base uses engineered prompt (1156 tok), LoRA uses minimal prompt (958 tok). This is by design (deployment benchmark), but means the comparison includes prompt effect.
3. **PC latency is irrelevant.** GPU inference time does not reflect RK3588 performance.
4. **Single run.** No confidence intervals. Results may vary with temperature sampling.

## 9. Recommendation

**Deploy 2B base on RK3588.** The LoRA adapter is effective (PC: 51.8% defect_type_exact) but its gains are destroyed by RKLLM W8A8 quantization (board: 0%). The most promising path to recover LoRA gains is:
1. **Merge LoRA into base model before RKLLM conversion** — this avoids runtime LoRA application and may preserve LoRA weights through quantization
2. **Test merged model on board** — if merged model retains LoRA quality, this is the optimal deployment strategy
3. If merged model also degrades, accept 2B base as the deployment model

## 10. Files

| File | Description |
|------|-------------|
| `pc_2b_base_vs_lora_eval.md` | This report |
| `pc_eval/metrics.json` | Structured metrics for both variants |
| `pc_eval/ab_eval_predictions_2B_2B_base_deployment.jsonl` | Per-sample base predictions |
| `pc_eval/ab_eval_predictions_2B_2B_lora_deployment.jsonl` | Per-sample LoRA predictions |
| `pc_eval/ab_eval_report_v2_deployment.json` | Original eval report |
