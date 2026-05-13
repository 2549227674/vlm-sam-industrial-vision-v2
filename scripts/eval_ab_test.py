#!/usr/bin/env python3
"""Stage 5.6: PC-side 4-variant evaluation (v2).

Two benchmark modes:
  1. deployment:  base + engineered prompt vs LoRA + minimal prompt
     (ships to RK3588, measures prompt-length advantage)
  2. method_control: base vs LoRA with identical prompt
     (isolates LoRA fine-tuning effect from prompt engineering)

Variants:
  2B_base: Qwen3-VL-2B base + engineered prompt (~300 tokens)
  2B_lora: Qwen3-VL-2B LoRA + minimal prompt (~50 tokens)
  4B_base: Qwen3-VL-4B base + engineered prompt (~300 tokens)
  4B_lora: Qwen3-VL-4B LoRA + minimal prompt (~50 tokens)

Method control:
  2B_base_same_prompt: Qwen3-VL-2B base + minimal prompt (~50 tokens)
  2B_lora_same_prompt: Qwen3-VL-2B LoRA + minimal prompt (~50 tokens)

Metrics:
  - json_parse_ok: valid JSON with all required keys
  - schema_ok: JSON passes DefectCreate schema constraints
  - category_exact: predicted category matches ground truth
  - defect_type_exact: predicted defect_type matches ground truth
  - severity_valid: severity in {low, medium, high}
  - bbox_iou_at_0_5: IoU >= 0.5 for at least one predicted bbox vs ground truth
  - prompt_tokens: number of input tokens
  - output_tokens: number of generated tokens

Usage:
    python scripts/eval_ab_test.py --model-size 2B --mode deployment
    python scripts/eval_ab_test.py --model-size 2B --mode method_control
    python scripts/eval_ab_test.py --model-size 4B --mode deployment
    python scripts/eval_ab_test.py --max-tokens 300
"""

import argparse
import json
from pathlib import Path

import torch
from peft import PeftModel
from PIL import Image
from tqdm import tqdm
from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = PROJECT_ROOT / "datasets" / "lora_split"
DEPLOYMENT_REPORT = PROJECT_ROOT / "results" / "ab_eval_report_v2_deployment.json"
METHOD_CONTROL_REPORT = PROJECT_ROOT / "results" / "ab_eval_report_v2_method_control.json"
CATEGORIES = [
    "bottle", "cable", "capsule", "carpet", "grid", "hazelnut", "leather",
    "metal_nut", "pill", "screw", "tile", "toothbrush", "transistor",
    "wood", "zipper",
]

VALID_SEVERITIES = {"low", "medium", "high"}

# Model paths per size
MODEL_PATHS = {
    "2B": {
        "base": PROJECT_ROOT / "models" / "qwen3vl_models" / "base",
        "lora": PROJECT_ROOT / "models" / "qwen3vl_lora_adapter_15cls",
    },
    "4B": {
        "base": PROJECT_ROOT / "models" / "qwen3vl_models" / "4b" / "base",
        "lora": PROJECT_ROOT / "models" / "qwen3vl_lora_4b_adapter",
    },
}

# Prompt A: engineered prompt for base models (no system message)
PROMPT_ENGINEERED = (
    "你是一个工业视觉质检专家。请仔细观察这张图片，检测其中的缺陷。\n"
    "你必须、一定、只能返回一个合法的 JSON 格式数据，绝对不要包含任何 markdown "
    "代码块标记，不要包含任何额外的问候语或解释。\n"
    "JSON 必须包含以下字段：\n"
    '- "category": 字符串，产品类别 (如 "metal_nut", "screw", "pill")\n'
    '- "defect_type": 字符串，缺陷类型 (如 "scratch", "bent")\n'
    '- "severity": 字符串，严重程度，只能是 "low", "medium", "high"\n'
    '- "confidence": 浮点数，置信度，范围 0.0 到 1.0\n'
    '- "bboxes": 列表，包含检测框字典[{"x": 中心点横坐标, "y": 中心点纵坐标, '
    '"w": 宽度, "h": 高度}]，所有坐标必须是 0 到 1 之间的归一化浮点数\n'
    '- "description": 字符串，对缺陷的中文描述。\n'
    "\n请严格遵守以上要求，现在请输出 JSON："
)

# Prompt B: minimal prompt for LoRA models (matches training format)
SYSTEM_MINIMAL = "你是一个工业视觉质检专家。"
USER_MINIMAL = (
    "请仔细观察这张图片，检测其中是否存在缺陷。如果存在，请严格输出包含 "
    "category, defect_type, severity, confidence, bboxes 和 description 的 JSON 报告。"
)

REQUIRED_KEYS = {"category", "defect_type", "severity", "confidence", "bboxes", "description"}


def compute_iou(box1: dict, box2: dict) -> float:
    """Compute IoU between two bboxes in {x, y, w, h} format (center coords)."""
    # Convert center to corner
    x1_min, y1_min = box1["x"] - box1["w"] / 2, box1["y"] - box1["h"] / 2
    x1_max, y1_max = box1["x"] + box1["w"] / 2, box1["y"] + box1["h"] / 2
    x2_min, y2_min = box2["x"] - box2["w"] / 2, box2["y"] - box2["h"] / 2
    x2_max, y2_max = box2["x"] + box2["w"] / 2, box2["y"] + box2["h"] / 2

    # Intersection
    xi_min = max(x1_min, x2_min)
    yi_min = max(y1_min, y2_min)
    xi_max = min(x1_max, x2_max)
    yi_max = min(y1_max, y2_max)
    inter = max(0, xi_max - xi_min) * max(0, yi_max - yi_min)

    # Union
    area1 = box1["w"] * box1["h"]
    area2 = box2["w"] * box2["h"]
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0.0


def evaluate_metrics(text: str, gt_data: dict | None) -> dict:
    """Evaluate all metrics for a single prediction."""
    metrics = {
        "json_parse_ok": False,
        "schema_ok": False,
        "category_exact": False,
        "defect_type_exact": False,
        "severity_valid": False,
        "bbox_iou_at_0_5": False,
    }

    # Extract JSON from output (handle <think>...</think> and other text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return metrics

    try:
        data = json.loads(text[start:end + 1])
    except (json.JSONDecodeError, AttributeError):
        return metrics

    # json_parse_ok: valid JSON with all required keys
    if not REQUIRED_KEYS.issubset(data.keys()):
        return metrics
    metrics["json_parse_ok"] = True

    # schema_ok: basic schema validation
    try:
        sev = data.get("severity", "")
        conf = float(data.get("confidence", -1))
        bboxes = data.get("bboxes", [])
        if (sev in VALID_SEVERITIES
            and 0.0 <= conf <= 1.0
            and isinstance(bboxes, list)
            and len(bboxes) <= 16
            and isinstance(data.get("category", ""), str)
            and isinstance(data.get("defect_type", ""), str)
            and isinstance(data.get("description", ""), str)):
            metrics["schema_ok"] = True
    except (ValueError, TypeError):
        pass

    # Ground-truth-dependent metrics
    if gt_data is None:
        return metrics

    # category_exact
    if data.get("category") == gt_data.get("category"):
        metrics["category_exact"] = True

    # defect_type_exact
    if data.get("defect_type") == gt_data.get("defect_type"):
        metrics["defect_type_exact"] = True

    # severity_valid (already checked in schema_ok, but also check vs GT)
    if data.get("severity") in VALID_SEVERITIES:
        metrics["severity_valid"] = True

    # bbox_iou_at_0_5: at least one predicted bbox has IoU >= 0.5 with any GT bbox
    pred_bboxes = data.get("bboxes", [])
    gt_bboxes = gt_data.get("bboxes", [])
    for pb in pred_bboxes:
        for gb in gt_bboxes:
            try:
                if compute_iou(pb, gb) >= 0.5:
                    metrics["bbox_iou_at_0_5"] = True
                    break
            except (KeyError, ZeroDivisionError):
                continue
        if metrics["bbox_iou_at_0_5"]:
            break

    return metrics


def run_inference(model, processor, image_path: Path, messages: list,
                  max_new_tokens: int = 200) -> tuple[str, int, int]:
    """Run inference, return (output_text, prompt_tokens, output_tokens)."""
    img = Image.open(image_path).convert("RGB")

    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[text], images=[img], padding=True,
                       return_tensors="pt").to(model.device)

    prompt_tokens = inputs.input_ids.shape[1]

    with torch.no_grad():
        generated = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)

    output_tokens = generated.shape[1] - prompt_tokens
    trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated)]
    output_text = processor.batch_decode(trimmed, skip_special_tokens=True,
                                         clean_up_tokenization_spaces=False)[0]
    return output_text, prompt_tokens, output_tokens


def load_gt_data(category: str, img_stem: str) -> dict | None:
    """Load ground-truth JSON annotation for an eval image."""
    # img_stem is like "scratch_000" -> look for scratch_000.json in train dir
    # But eval images are in eval/, GT is from the original annotation
    # We try to find the JSON in the eval dir first, then train dir
    for split in ("eval", "train"):
        json_path = EVAL_DIR / category / split / f"{img_stem}.json"
        if json_path.exists():
            try:
                with open(json_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return None
    return None


def collect_eval_samples() -> list[dict]:
    samples = []
    for cat in CATEGORIES:
        eval_dir = EVAL_DIR / cat / "eval"
        if not eval_dir.exists():
            continue
        for img_path in sorted(eval_dir.glob("*.png")):
            gt = load_gt_data(cat, img_path.stem)
            samples.append({"category": cat, "path": img_path, "gt": gt})
    return samples


def evaluate_variant(model, processor, samples: list[dict],
                     variant: str, max_new_tokens: int,
                     use_engineered_prompt: bool) -> dict:
    """Run one variant over all samples, return per-category metrics."""
    cat_metrics = {cat: {
        "json_parse_ok": 0, "schema_ok": 0, "category_exact": 0,
        "defect_type_exact": 0, "severity_valid": 0, "bbox_iou_at_0_5": 0,
        "total": 0, "prompt_tokens_sum": 0, "output_tokens_sum": 0,
    } for cat in CATEGORIES}

    for sample in tqdm(samples, desc=f"Variant {variant}"):
        cat = sample["category"]
        cat_metrics[cat]["total"] += 1

        if use_engineered_prompt:
            messages = [{"role": "user", "content": [
                {"type": "image", "image": str(sample["path"])},
                {"type": "text", "text": PROMPT_ENGINEERED},
            ]}]
        else:
            messages = [
                {"role": "system", "content": SYSTEM_MINIMAL},
                {"role": "user", "content": [
                    {"type": "image", "image": str(sample["path"])},
                    {"type": "text", "text": USER_MINIMAL},
                ]},
            ]

        out_text, p_tokens, o_tokens = run_inference(
            model, processor, sample["path"], messages, max_new_tokens)

        metrics = evaluate_metrics(out_text, sample["gt"])
        cat_metrics[cat]["prompt_tokens_sum"] += p_tokens
        cat_metrics[cat]["output_tokens_sum"] += o_tokens
        for k in ("json_parse_ok", "schema_ok", "category_exact",
                  "defect_type_exact", "severity_valid", "bbox_iou_at_0_5"):
            if metrics[k]:
                cat_metrics[cat][k] += 1

    return cat_metrics


def build_report(cat_metrics: dict, variant: str) -> dict:
    """Build a structured report dict for one variant."""
    report = {"variant": variant, "categories": {}, "total": {}}
    totals = {k: 0 for k in ("json_parse_ok", "schema_ok", "category_exact",
                              "defect_type_exact", "severity_valid",
                              "bbox_iou_at_0_5", "total",
                              "prompt_tokens_sum", "output_tokens_sum")}

    for cat in CATEGORIES:
        m = cat_metrics[cat]
        n = m["total"]
        if n == 0:
            continue
        cat_report = {}
        for k in ("json_parse_ok", "schema_ok", "category_exact",
                  "defect_type_exact", "severity_valid", "bbox_iou_at_0_5"):
            cat_report[k] = f"{m[k]}/{n}"
            cat_report[f"{k}_rate"] = round(m[k] / n * 100, 1)
            totals[k] += m[k]
        cat_report["avg_prompt_tokens"] = round(m["prompt_tokens_sum"] / n, 1)
        cat_report["avg_output_tokens"] = round(m["output_tokens_sum"] / n, 1)
        cat_report["total"] = n
        report["categories"][cat] = cat_report
        totals["total"] += n
        totals["prompt_tokens_sum"] += m["prompt_tokens_sum"]
        totals["output_tokens_sum"] += m["output_tokens_sum"]

    n = totals["total"]
    if n > 0:
        for k in ("json_parse_ok", "schema_ok", "category_exact",
                  "defect_type_exact", "severity_valid", "bbox_iou_at_0_5"):
            report["total"][k] = f"{totals[k]}/{n}"
            report["total"][f"{k}_rate"] = round(totals[k] / n * 100, 1)
        report["total"]["avg_prompt_tokens"] = round(totals["prompt_tokens_sum"] / n, 1)
        report["total"]["avg_output_tokens"] = round(totals["output_tokens_sum"] / n, 1)
        report["total"]["total"] = n

    return report


def print_report(report: dict) -> None:
    """Print a markdown table from a report dict."""
    variant = report["variant"]
    print(f"\n{'=' * 90}")
    print(f"  Variant: {variant}")
    print(f"{'=' * 90}")

    header = (f"| {'Category':12s} | {'JSON OK':>10s} | {'Schema':>10s} | "
              f"{'CatExact':>10s} | {'DefType':>10s} | {'SevValid':>10s} | "
              f"{'BBoxIoU':>10s} |")
    print(header)
    print(f"|{'-' * 13}|{'-' * 11}|{'-' * 11}|{'-' * 11}|{'-' * 11}|{'-' * 11}|{'-' * 11}|")

    for cat in CATEGORIES:
        if cat not in report["categories"]:
            continue
        c = report["categories"][cat]
        print(f"| {cat:12s} | {c['json_parse_ok']:>10s} | {c['schema_ok']:>10s} | "
              f"{c['category_exact']:>10s} | {c['defect_type_exact']:>10s} | "
              f"{c['severity_valid']:>10s} | {c['bbox_iou_at_0_5']:>10s} |")

    t = report["total"]
    if t:
        print(f"|{'-' * 13}|{'-' * 11}|{'-' * 11}|{'-' * 11}|{'-' * 11}|{'-' * 11}|{'-' * 11}|")
        print(f"| {'TOTAL':12s} | {t['json_parse_ok']:>10s} | {t['schema_ok']:>10s} | "
              f"{t['category_exact']:>10s} | {t['defect_type_exact']:>10s} | "
              f"{t['severity_valid']:>10s} | {t['bbox_iou_at_0_5']:>10s} |")
        print(f"\n  Avg prompt tokens: {t.get('avg_prompt_tokens', 'N/A')}")
        print(f"  Avg output tokens: {t.get('avg_output_tokens', 'N/A')}")
    print("=" * 90)


def run_deployment_benchmark(model, processor, samples: list[dict],
                             size: str, max_new_tokens: int) -> dict:
    """Deployment benchmark: base + engineered prompt vs LoRA + minimal prompt."""
    base_variant = f"{size}_base"
    lora_variant = f"{size}_lora"

    print(f"\n--- Deployment: {base_variant} (base + engineered prompt) ---")
    counts_base = evaluate_variant(model, processor, samples, base_variant,
                                   max_new_tokens, use_engineered_prompt=True)
    report_base = build_report(counts_base, base_variant)
    print_report(report_base)

    print(f"\nLoading LoRA adapter: {MODEL_PATHS[size]['lora']}")
    lora_model = PeftModel.from_pretrained(model, str(MODEL_PATHS[size]["lora"]))
    lora_model.eval()

    print(f"\n--- Deployment: {lora_variant} (LoRA + minimal prompt) ---")
    counts_lora = evaluate_variant(lora_model, processor, samples, lora_variant,
                                   max_new_tokens, use_engineered_prompt=False)
    report_lora = build_report(counts_lora, lora_variant)
    print_report(report_lora)

    return {"benchmark": "deployment", "variants": [report_base, report_lora]}


def run_method_control_benchmark(model, processor, samples: list[dict],
                                 size: str, max_new_tokens: int) -> dict:
    """Method control: base vs LoRA with identical minimal prompt."""
    base_variant = f"{size}_base_same_prompt"
    lora_variant = f"{size}_lora_same_prompt"

    print(f"\n--- Method Control: {base_variant} (base + minimal prompt) ---")
    counts_base = evaluate_variant(model, processor, samples, base_variant,
                                   max_new_tokens, use_engineered_prompt=False)
    report_base = build_report(counts_base, base_variant)
    print_report(report_base)

    print(f"\nLoading LoRA adapter: {MODEL_PATHS[size]['lora']}")
    lora_model = PeftModel.from_pretrained(model, str(MODEL_PATHS[size]["lora"]))
    lora_model.eval()

    print(f"\n--- Method Control: {lora_variant} (LoRA + minimal prompt) ---")
    counts_lora = evaluate_variant(lora_model, processor, samples, lora_variant,
                                   max_new_tokens, use_engineered_prompt=False)
    report_lora = build_report(counts_lora, lora_variant)
    print_report(report_lora)

    return {"benchmark": "method_control", "variants": [report_base, report_lora]}


def main() -> None:
    parser = argparse.ArgumentParser(description="4-variant evaluation for Qwen3-VL")
    parser.add_argument("--model-size", choices=["2B", "4B"], required=True,
                        help="Model size to evaluate (2B or 4B)")
    parser.add_argument("--mode", choices=["deployment", "method_control", "both"],
                        default="both", help="Benchmark mode")
    parser.add_argument("--max-tokens", type=int, default=200)
    parser.add_argument("--lora-adapter-path", type=str, default=None,
                        help="Override LoRA adapter path (default: models/qwen3vl_lora_adapter_15cls for 2B)")
    args = parser.parse_args()

    size = args.model_size
    paths = MODEL_PATHS[size].copy()
    if args.lora_adapter_path:
        paths["lora"] = Path(args.lora_adapter_path)

    samples = collect_eval_samples()
    print(f"Eval samples: {len(samples)}")
    print(f"Model size: {size}")
    print(f"Mode: {args.mode}")

    # Load base model
    print(f"\nLoading base model: {paths['base']}")
    processor = AutoProcessor.from_pretrained(str(paths["base"]))
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        str(paths["base"]), dtype=torch.bfloat16,
        device_map="auto",
    )
    model.eval()

    results = []

    if args.mode in ("deployment", "both"):
        result = run_deployment_benchmark(model, processor, samples, size, args.max_tokens)
        results.append(result)
        # Save deployment report
        DEPLOYMENT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        with open(DEPLOYMENT_REPORT, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\nDeployment report saved: {DEPLOYMENT_REPORT}")

    if args.mode in ("method_control", "both"):
        # Reload base model (LoRA was attached in deployment benchmark)
        if args.mode == "both":
            print(f"\nReloading base model for method control: {paths['base']}")
            model = Qwen3VLForConditionalGeneration.from_pretrained(
                str(paths["base"]), dtype=torch.bfloat16,
                device_map="auto",
            )
            model.eval()

        result = run_method_control_benchmark(model, processor, samples, size, args.max_tokens)
        results.append(result)
        # Save method control report
        METHOD_CONTROL_REPORT.parent.mkdir(parents=True, exist_ok=True)
        with open(METHOD_CONTROL_REPORT, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\nMethod control report saved: {METHOD_CONTROL_REPORT}")

    print("\nAll evaluations complete.")


if __name__ == "__main__":
    main()
