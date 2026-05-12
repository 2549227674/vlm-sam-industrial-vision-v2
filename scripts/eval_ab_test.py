#!/usr/bin/env python3
"""Stage 5.6: PC-side 4-variant evaluation (v2).

Variants:
  2B_base: Qwen3-VL-2B base + engineered prompt (~300 tokens)
  2B_lora: Qwen3-VL-2B LoRA + minimal prompt (~50 tokens)
  4B_base: Qwen3-VL-4B base + engineered prompt (~300 tokens)
  4B_lora: Qwen3-VL-4B LoRA + minimal prompt (~50 tokens)

Metric: JSON parse success rate (all required fields present).

Usage:
    python scripts/eval_ab_test.py --model-size 2B
    python scripts/eval_ab_test.py --model-size 4B
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
REPORT_PATH = PROJECT_ROOT / "results" / "ab_eval_report_v2.json"
CATEGORIES = [
    "bottle", "cable", "capsule", "carpet", "grid", "hazelnut", "leather",
    "metal_nut", "pill", "screw", "tile", "toothbrush", "transistor",
    "wood", "zipper",
]

# Model paths per size
MODEL_PATHS = {
    "2B": {
        "base": PROJECT_ROOT / "models" / "qwen3vl_models" / "base",
        "lora": PROJECT_ROOT / "models" / "qwen3vl_lora_adapter",
    },
    "4B": {
        "base": PROJECT_ROOT / "models" / "qwen3vl_models" / "4b" / "base",
        "lora": PROJECT_ROOT / "models" / "qwen3vl_lora_4b_adapter",
    },
}

# Variant A: base model needs detailed instruction (no system message)
PROMPT_A = (
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

# Variant B: LoRA model uses same system+user format as training
SYSTEM_B = "你是一个工业视觉质检专家。"
USER_B = (
    "请仔细观察这张图片，检测其中是否存在缺陷。如果存在，请严格输出包含 "
    "category, defect_type, severity, confidence, bboxes 和 description 的 JSON 报告。"
)

REQUIRED_KEYS = {"category", "defect_type", "severity", "confidence", "bboxes", "description"}


def check_json_compliance(text: str) -> bool:
    """Extract JSON from model output (ignoring </think> etc.) and validate."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return False

    try:
        data = json.loads(text[start:end + 1])
        return REQUIRED_KEYS.issubset(data.keys())
    except (json.JSONDecodeError, AttributeError):
        return False


def run_inference(model, processor, image_path: Path, messages: list,
                  max_new_tokens: int = 200) -> str:
    img = Image.open(image_path).convert("RGB")

    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[text], images=[img], padding=True,
                       return_tensors="pt").to(model.device)

    with torch.no_grad():
        generated = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)

    trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated)]
    return processor.batch_decode(trimmed, skip_special_tokens=True,
                                  clean_up_tokenization_spaces=False)[0]


def collect_eval_samples() -> list[dict]:
    samples = []
    for cat in CATEGORIES:
        eval_dir = EVAL_DIR / cat / "eval"
        if not eval_dir.exists():
            continue
        for img_path in sorted(eval_dir.glob("*.png")):
            samples.append({"category": cat, "path": img_path})
    return samples


def evaluate_variant(model, processor, samples: list[dict],
                     variant: str, max_new_tokens: int) -> dict:
    """Run one variant over all samples, return per-category counts."""
    counts = {cat: {"ok": 0, "total": 0} for cat in CATEGORIES}

    for sample in tqdm(samples, desc=f"Variant {variant}"):
        cat = sample["category"]
        counts[cat]["total"] += 1

        if "base" in variant:
            messages = [{"role": "user", "content": [
                {"type": "image", "image": str(sample["path"])},
                {"type": "text", "text": PROMPT_A},
            ]}]
        else:
            messages = [
                {"role": "system", "content": SYSTEM_B},
                {"role": "user", "content": [
                    {"type": "image", "image": str(sample["path"])},
                    {"type": "text", "text": USER_B},
                ]},
            ]

        out_text = run_inference(model, processor, sample["path"],
                                 messages, max_new_tokens)
        if check_json_compliance(out_text):
            counts[cat]["ok"] += 1

    return counts


def print_report(counts_a: dict, counts_b: dict,
                 variant_a: str = "base", variant_b: str = "lora") -> dict:
    """Print markdown table and return structured report dict."""
    print(f"\n{'=' * 70}")
    print(f"  Stage 5.6: Evaluation Report (JSON Parse Success Rate)")
    print("=" * 70)
    va_short = variant_a.replace("_", " ").title()
    vb_short = variant_b.replace("_", " ").title()
    header = f"| {'Category':10s} | {va_short:18s} | {vb_short:18s} | {'Delta':7s} |"
    print(header)
    print(f"|{'-' * 11}|{'-' * 20}|{'-' * 20}|{'-' * 9}|")

    report = {"categories": {}, "total": {}}
    tot_a, tot_b, tot_n = 0, 0, 0

    for cat in CATEGORIES:
        n = counts_a[cat]["total"]
        if n == 0:
            continue
        a, b = counts_a[cat]["ok"], counts_b[cat]["ok"]
        tot_a += a
        tot_b += b
        tot_n += n
        ra, rb = a / n * 100, b / n * 100
        print(f"| {cat:10s} | {a:3d}/{n:3d} ({ra:5.1f}%)    | "
              f"{b:3d}/{n:3d} ({rb:5.1f}%)    | {rb - ra:+5.1f}% |")
        report["categories"][cat] = {variant_a: f"{a}/{n}", variant_b: f"{b}/{n}",
                                     f"rate_{variant_a}": round(ra, 1),
                                     f"rate_{variant_b}": round(rb, 1)}

    ra_t = tot_a / tot_n * 100 if tot_n else 0
    rb_t = tot_b / tot_n * 100 if tot_n else 0
    print(f"| {'TOTAL':10s} | {tot_a:3d}/{tot_n:3d} ({ra_t:5.1f}%) | "
          f"{tot_b:3d}/{tot_n:3d} ({rb_t:5.1f}%) | {rb_t - ra_t:+5.1f}% |")
    print("=" * 70)

    report["total"] = {variant_a: f"{tot_a}/{tot_n}", variant_b: f"{tot_b}/{tot_n}",
                       f"rate_{variant_a}": round(ra_t, 1),
                       f"rate_{variant_b}": round(rb_t, 1)}
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="4-variant evaluation for Qwen3-VL")
    parser.add_argument("--model-size", choices=["2B", "4B"], required=True,
                        help="Model size to evaluate (2B or 4B)")
    parser.add_argument("--max-tokens", type=int, default=200)
    args = parser.parse_args()

    size = args.model_size
    paths = MODEL_PATHS[size]
    base_variant = f"{size}_base"
    lora_variant = f"{size}_lora"

    samples = collect_eval_samples()
    print(f"Eval samples: {len(samples)}")
    print(f"Model size: {size}")

    # Load base model
    print(f"\nLoading base model: {paths['base']}")
    processor = AutoProcessor.from_pretrained(str(paths["base"]))
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        str(paths["base"]), dtype=torch.bfloat16,
        device_map="auto",
    )
    model.eval()

    # Variant: base model + engineered prompt
    print(f"\n--- Variant {base_variant}: Base + engineered prompt ---")
    counts_base = evaluate_variant(model, processor, samples, base_variant, args.max_tokens)

    # Variant: attach LoRA adapter
    print(f"\nLoading LoRA adapter: {paths['lora']}")
    model = PeftModel.from_pretrained(model, str(paths["lora"]))
    model.eval()

    print(f"--- Variant {lora_variant}: LoRA + minimal prompt ---")
    counts_lora = evaluate_variant(model, processor, samples, lora_variant, args.max_tokens)

    # Report
    report = print_report(counts_base, counts_lora, base_variant, lora_variant)

    # Save report
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nReport saved: {REPORT_PATH}")


if __name__ == "__main__":
    main()
