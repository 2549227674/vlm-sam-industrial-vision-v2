#!/usr/bin/env python3
"""OPRO-style prompt-only baseline for Qwen3-VL.

Generates multiple prompt candidates via LLM meta-prompt, evaluates each on a
small train subset, then selects the best prompt and evaluates on the held-out
eval set.

This is a lightweight method-control experiment — no parameter fine-tuning,
no RK3588 deployment chain involvement. PC-stage only.

Usage:
    python scripts/optimize_prompt_opro.py --model-size 2B
    python scripts/optimize_prompt_opro.py --model-size 2B --num-candidates 5
    python scripts/optimize_prompt_opro.py --model-size 2B --train-subset-size 30
"""

import argparse
import json
import re
from pathlib import Path

import torch
from PIL import Image
from tqdm import tqdm
from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRAIN_DIR = PROJECT_ROOT / "datasets" / "lora_split"
EVAL_DIR = PROJECT_ROOT / "datasets" / "lora_split"
RESULTS_DIR = PROJECT_ROOT / "results"
BEST_PROMPT_PATH = RESULTS_DIR / "prompt_opro_best.json"

CATEGORIES = [
    "bottle", "cable", "capsule", "carpet", "grid", "hazelnut", "leather",
    "metal_nut", "pill", "screw", "tile", "toothbrush", "transistor",
    "wood", "zipper",
]

VALID_SEVERITIES = {"low", "medium", "high"}
REQUIRED_KEYS = {"category", "defect_type", "severity", "confidence", "bboxes", "description"}

MODEL_PATHS = {
    "2B": PROJECT_ROOT / "models" / "qwen3vl_models" / "base",
    "4B": PROJECT_ROOT / "models" / "qwen3vl_models" / "4b" / "base",
}

# Seed prompt (baseline)
SEED_PROMPT = (
    "请仔细观察这张图片，检测其中是否存在缺陷。如果存在，请严格输出包含 "
    "category, defect_type, severity, confidence, bboxes 和 description 的 JSON 报告。"
)

SYSTEM_PROMPT = "你是一个工业视觉质检专家。"

# Meta-prompt for generating prompt candidates
META_PROMPT = """你是一个 AI prompt 工程专家。你的任务是为工业视觉缺陷检测模型设计更好的 prompt。

当前使用的 prompt 是：
"{current_prompt}"

请生成 {n} 个改进版本的 prompt。每个版本应该：
1. 保持要求输出 JSON 格式（含 category, defect_type, severity, confidence, bboxes, description）
2. 尝试不同的策略：更明确的指令、更好的结构引导、few-shot 示例提示等
3. 长度控制在 30-200 字之间

请以 JSON 数组格式输出，每个元素是一个改进后的 prompt 字符串：
["prompt1", "prompt2", ...]

只输出 JSON 数组，不要输出其他内容。"""


def extract_json_array(text: str) -> list[str]:
    """Extract JSON array from model output."""
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []


def evaluate_prompt(model, processor, samples: list[dict],
                    prompt: str, max_new_tokens: int = 200) -> float:
    """Evaluate a prompt on a set of samples, return JSON parse success rate."""
    ok = 0
    total = 0

    for sample in tqdm(samples, desc="Evaluating", leave=False):
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "image", "image": str(sample["path"])},
                {"type": "text", "text": prompt},
            ]},
        ]

        img = Image.open(sample["path"]).convert("RGB")
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[text], images=[img], padding=True,
                           return_tensors="pt").to(model.device)

        with torch.no_grad():
            generated = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)

        trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated)]
        output = processor.batch_decode(trimmed, skip_special_tokens=True,
                                        clean_up_tokenization_spaces=False)[0]

        total += 1
        start = output.find("{")
        end = output.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(output[start:end + 1])
                if REQUIRED_KEYS.issubset(data.keys()):
                    ok += 1
            except json.JSONDecodeError:
                pass

    return ok / total if total > 0 else 0.0


def collect_samples(split: str, max_per_category: int = 20) -> list[dict]:
    """Collect samples from a split, limited per category."""
    samples = []
    for cat in CATEGORIES:
        split_dir = TRAIN_DIR / cat / split
        if not split_dir.exists():
            continue
        count = 0
        for img_path in sorted(split_dir.glob("*.png")):
            if count >= max_per_category:
                break
            samples.append({"category": cat, "path": img_path})
            count += 1
    return samples


def generate_candidates(model, processor, current_prompt: str,
                        num_candidates: int = 5) -> list[str]:
    """Use the model itself to generate prompt candidates (OPRO style)."""
    meta = META_PROMPT.format(current_prompt=current_prompt, n=num_candidates)
    messages = [{"role": "user", "content": meta}]

    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = processor(text=[text], padding=True, return_tensors="pt").to(model.device)

    with torch.no_grad():
        generated = model.generate(**inputs, max_new_tokens=1000, do_sample=True, temperature=0.8)

    trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated)]
    output = processor.batch_decode(trimmed, skip_special_tokens=True,
                                    clean_up_tokenization_spaces=False)[0]

    candidates = extract_json_array(output)
    # Filter to reasonable-length strings
    return [c for c in candidates if isinstance(c, str) and 10 < len(c) < 500]


def main() -> None:
    parser = argparse.ArgumentParser(description="OPRO-style prompt optimization")
    parser.add_argument("--model-size", choices=["2B", "4B"], default="2B")
    parser.add_argument("--num-candidates", type=int, default=5,
                        help="Number of prompt candidates per iteration")
    parser.add_argument("--num-iterations", type=int, default=3,
                        help="Number of OPRO iterations")
    parser.add_argument("--train-subset-size", type=int, default=30,
                        help="Number of samples for prompt search (per category)")
    parser.add_argument("--eval-subset-size", type=int, default=20,
                        help="Number of eval samples per category")
    parser.add_argument("--max-tokens", type=int, default=200)
    args = parser.parse_args()

    print(f"Model size: {args.model_size}")
    print(f"OPRO iterations: {args.num_iterations}")
    print(f"Candidates per iteration: {args.num_candidates}")

    # Load model
    model_path = MODEL_PATHS[args.model_size]
    print(f"\nLoading model: {model_path}")
    processor = AutoProcessor.from_pretrained(str(model_path))
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        str(model_path), dtype=torch.bfloat16, device_map="auto",
    )
    model.eval()

    # Collect train subset for prompt search
    train_samples = collect_samples("train", max_per_category=args.train_subset_size)
    print(f"Train subset: {len(train_samples)} samples")

    # Collect eval set (held-out, never used during search)
    eval_samples = collect_samples("eval", max_per_category=args.eval_subset_size)
    print(f"Eval set: {len(eval_samples)} samples")

    # OPRO loop
    current_prompt = SEED_PROMPT
    best_prompt = SEED_PROMPT
    best_score = 0.0
    history = []

    # Evaluate seed prompt
    print(f"\n--- Evaluating seed prompt ---")
    seed_score = evaluate_prompt(model, processor, train_samples, current_prompt, args.max_tokens)
    print(f"Seed prompt score: {seed_score:.1%}")
    best_score = seed_score
    history.append({"iteration": 0, "prompt": current_prompt, "train_score": seed_score})

    for iteration in range(1, args.num_iterations + 1):
        print(f"\n{'=' * 60}")
        print(f"  OPRO Iteration {iteration}/{args.num_iterations}")
        print(f"{'=' * 60}")

        # Generate candidates
        print("Generating prompt candidates...")
        candidates = generate_candidates(model, processor, current_prompt, args.num_candidates)
        print(f"Generated {len(candidates)} candidates")

        if not candidates:
            print("No candidates generated, stopping early")
            break

        # Evaluate each candidate
        for i, candidate in enumerate(candidates):
            print(f"\n--- Candidate {i+1}/{len(candidates)} ---")
            print(f"  Prompt: {candidate[:80]}...")
            score = evaluate_prompt(model, processor, train_samples, candidate, args.max_tokens)
            print(f"  Score: {score:.1%}")
            history.append({"iteration": iteration, "prompt": candidate, "train_score": score})

            if score > best_score:
                best_score = score
                best_prompt = candidate
                print(f"  ** New best! ({score:.1%})")

        current_prompt = best_prompt
        print(f"\nBest so far: {best_score:.1%}")

    # Final evaluation on held-out eval set
    print(f"\n{'=' * 60}")
    print(f"  Final Evaluation on Held-out Eval Set")
    print(f"{'=' * 60}")
    eval_score = evaluate_prompt(model, processor, eval_samples, best_prompt, args.max_tokens)
    print(f"Eval score: {eval_score:.1%}")

    # Save results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result = {
        "model_size": args.model_size,
        "best_prompt": best_prompt,
        "train_score": best_score,
        "eval_score": eval_score,
        "seed_prompt": SEED_PROMPT,
        "seed_train_score": seed_score,
        "iterations": args.num_iterations,
        "history": history,
    }
    with open(BEST_PROMPT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved: {BEST_PROMPT_PATH}")
    print(f"Best prompt: {best_prompt}")
    print(f"Train score: {best_score:.1%}")
    print(f"Eval score:  {eval_score:.1%}")


if __name__ == "__main__":
    main()
