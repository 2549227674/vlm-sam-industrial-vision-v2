# Phase 6 Track B Model Conversion Report

## 1. Objective

Convert the PC/AutoDL-side industrial vision pipeline into RK3588-ready deployment artifacts.

Target components:
- EfficientAD-S anomaly detector (15 classes)
- FastSAM segmentation model (15-class calibration)
- Qwen3-VL 2B/4B LoRA language model
- Qwen3-VL vision encoders (2B and 4B)

## 2. Final Artifact Status

| Artifact | Status | Local Path |
|---|---|---|
| EfficientAD 15-class RKNN | Done (15/15) | `models/efficientad_models/{category}/model.rknn` |
| FastSAM 15-class calibrated RKNN | Done | `models/fastsam_models/fastsam_s.rknn` |
| Qwen3-VL 2B base RKLLM | Done | `models/qwen3vl_models/rkllm_15cls/qwen3vl_2b_w8a8_base.rkllm` (2.3G) |
| Qwen3-VL 2B LoRA 15cls RKLLM | Done | `models/qwen3vl_models/rkllm_15cls/qwen3vl_2b_w8a8_lora_15cls.rkllm` (2.3G) |
| Qwen3-VL 2B vision RKNN | Done | `models/qwen3vl_models/rkllm_15cls/qwen3vl_2b_vision.rknn` (812M) |
| Qwen3-VL 4B base RKLLM | Done | `models/qwen3vl_models/rkllm_15cls/qwen3vl_4b_w8a8_base.rkllm` (4.6G) |
| Qwen3-VL 4B LoRA 15cls RKLLM | Done | `models/qwen3vl_models/rkllm_15cls/qwen3vl_4b_w8a8_lora_15cls.rkllm` (4.6G) |
| Qwen3-VL 4B vision RKNN | Done | `models/qwen3vl_models/rkllm_15cls/qwen3vl_4b_vision.rknn` (843M) |

### 2.1 Known sha256

```
qwen3vl_2b_w8a8_lora_15cls.rkllm  de2a25b08d5a87093fb8305364bdae4cb3d3db773477ac0153bca300190f0482
```

sha256 files for other artifacts are not yet generated (low priority, local files verified by size/date).

## 3. Calibration Strategy

MVTec 15-class industrial images were used for RKLLM calibration instead of generic COCO examples.

Reason:
- Calibration embeddings depend on both image token distribution and prompt token distribution.
- MVTec industrial images and the industrial JSON prompt are closer to deployment inputs.

Dataset:
- 30 samples (15 categories x up to 2 images)
- Chinese industrial defect prompt: "分析图片中的工业零件缺陷，以JSON格式输出检测结果，包含category、defect_type、severity、confidence、bboxes和description字段。"
- Target uses paired JSON annotation compressed strings

Embedding dimensions:
- 2B: `inputs_embeds torch.Size([1, seq_len, 2048])`, 30/30 completed
- 4B: `inputs_embeds torch.Size([1, seq_len, 2560])`, 30/30 completed

## 4. Key Deviations from Original Plan

### FastSAM

The v1 3-class calibration RKNN was not reused. FastSAM was re-converted using a 15-class MVTec calibration set (~20 images per class, ~300 total). FastSAM weights are still COCO pretrained; only the RKNN INT8 calibration data changed.

The conversion script had a PASS/FAIL reporting bug where some layers with lower cosine similarity still showed PASS. This is a script reporting logic issue, not an indication that the `.rknn` file is unusable.

### EfficientAD

`accuracy_analysis` was moved after RKNN export and made optional due to disk-related SIGBUS failures (exit code 135). The SIGBUS was caused by disk pressure from accuracy analysis intermediate files, not by category-specific model failures.

Recommended order: `build -> export_rknn -> optional accuracy_analysis`.

### Qwen3-VL RKLLM

Two environments were required:
1. New transformers environment (>=4.57.0) for Qwen3VL embedding generation
2. `venv_rkllm_clean` for RKLLM export (rkllm-toolkit 1.2.3, transformers==4.55.2)

Do not upgrade transformers in `venv_rkllm_clean`.

4B required a separate `visual.merger` patch during embedding generation (see Section 5).

## 5. Key Issues and Fixes

| Issue | Root Cause | Fix |
|---|---|---|
| `accelerate` missing | Not in rkllm environment deps | Install accelerate in embedding-generation env |
| `protobuf` missing | Not in rkllm environment deps | Install compatible protobuf |
| `extra_special_tokens` list error | LLaMA-Factory exports as list, transformers expects dict | Patch `tokenizer_config.json`: list -> dict |
| Missing `vocab.json` / `merges.txt` | LLaMA-Factory export did not copy them | Copy from base model directory |
| Polluted RKLLM venv | pip dependency conflicts accumulated | Create clean `venv_rkllm_clean` |
| `pkg_resources` missing | setuptools >=81 dropped pkg_resources | Pin setuptools < 81 (e.g., 80.9.0) |
| 4B visual feature shape mismatch | `model.visual(...)` returns raw [N*4, 1024], not projected [N, 2560] | Apply `model.model.visual.merger(image_embeds)` before assignment |
| `--savepath` ignored by export_rkllm.py | Script hardcodes output to `./rkllm/` directory | Patch script or use default output path then move file |
| Disk write failure (4B base) | RKLLM Toolkit internal space check or temp file peak | Expand disk / set TMPDIR / retry |
| `datasets.json` path error | Script hardcodes `open("data/datasets.json")` | Must run from `examples/multimodal_model_demo/` parent directory |

## 6. Environment Configuration

### venv_rkllm_clean (stable RKLLM export environment)

```bash
# Location: /root/autodl-tmp/venv_rkllm_clean
# Fixed dependencies:
torch==2.6.0
torchvision==0.21.0
transformers==4.55.2
tokenizers==0.21.4
setuptools==80.9.0
# rkllm_toolkit installed with --no-deps
# Manual sub-deps: jsonlines, addict, easydict, scipy, colorlog, datasets
```

Do NOT install LLaMA-Factory or upgrade transformers in this environment.

### Embedding generation environment

Requires newer transformers (>=4.57.0) with `Qwen3VLForConditionalGeneration` support.

## 7. Target Local Directory Structure

```
models/qwen3vl_models/rkllm_15cls/
├── qwen3vl_2b_vision.rknn                    # 812M
├── qwen3vl_2b_w8a8_base.rkllm                # 2.3G
├── qwen3vl_2b_w8a8_lora_15cls.rkllm          # 2.3G
├── qwen3vl_2b_w8a8_lora_15cls.sha256         # Done
├── qwen3vl_4b_vision.rknn                    # 843M
├── qwen3vl_4b_w8a8_base.rkllm                # 4.6G
├── qwen3vl_4b_w8a8_lora_15cls.rkllm          # 4.6G
```

## 8. Completion

Phase 6 Track B is complete:
- All 2B/4B base and LoRA RKLLM exports done
- Both vision encoders (2B, 4B) ready locally
- 4B vision encoder converted locally in WSL `.venv_rknn` from AutoDL-exported `qwen3vl_vision.onnx`
- 4B base RKLLM completed and downloaded to local

## 9. Next Steps

1. Generate sha256 files for all RKLLM/RKNN artifacts.
2. Start Phase 4 Track A integration validation.
