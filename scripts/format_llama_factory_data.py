#!/usr/bin/env python3
"""Convert per-image JSON annotations to LLaMA-Factory ShareGPT multimodal format.

Reads:  datasets/lora_split/{category}/{train,eval}/*.png + *.json
Writes: datasets/industrial_vision_train.json  (ShareGPT format)
        datasets/industrial_vision_eval.json   (ShareGPT format)
        datasets/dataset_info.json              (LLaMA-Factory registry)
        datasets/README.md                      (usage instructions)

Training command (run from project root):
    llamafactory-cli train \\
        --dataset_dir datasets/ \\
        --dataset industrial_vision \\
        --model_name_or_path models/qwen3vl_models/base/ \\
        ...

Image paths are relative to project root so the dataset is portable.
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPLIT_DIR = PROJECT_ROOT / "datasets" / "lora_split"
OUTPUT_DIR = PROJECT_ROOT / "datasets"

# MVTec AD 全 15 类白名单
VALID_CATEGORIES = {
    "bottle", "cable", "capsule", "carpet", "grid", "hazelnut", "leather",
    "metal_nut", "pill", "screw", "tile", "toothbrush", "transistor",
    "wood", "zipper",
}

SYSTEM_PROMPT = "你是一个工业视觉质检专家。"
USER_PROMPT = (
    "请仔细观察这张图片，检测其中是否存在缺陷。"
    "如果存在，请严格输出包含 category, defect_type, severity, "
    "confidence, bboxes 和 description 的 JSON 报告。"
)


def discover_categories() -> list[str]:
    """Auto-discover categories from datasets/lora_split/ directory."""
    if not SPLIT_DIR.exists():
        print(f"[ERROR] Split directory not found: {SPLIT_DIR}")
        print("  Run scripts/split_lora_data.py first.")
        sys.exit(1)

    cats = sorted(
        d.name for d in SPLIT_DIR.iterdir()
        if d.is_dir() and d.name in VALID_CATEGORIES
    )
    if not cats:
        print(f"[ERROR] No valid categories found in {SPLIT_DIR}")
        sys.exit(1)

    unknown = set(
        d.name for d in SPLIT_DIR.iterdir()
        if d.is_dir() and d.name not in VALID_CATEGORIES
    )
    if unknown:
        print(f"[WARN] Ignoring directories not in 15-class whitelist: {unknown}")

    return cats


def validate_json(json_path: Path) -> dict | None:
    """Load and validate a JSON annotation file."""
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [WARN] Invalid JSON {json_path}: {e}")
        return None

    # Check category is in whitelist
    cat = data.get("category", "")
    if cat not in VALID_CATEGORIES:
        print(f"  [WARN] Invalid category '{cat}' in {json_path}")
        return None

    return data


def build_conversation(img_path: Path, json_path: Path, rel_base: Path) -> dict | None:
    """Build a single ShareGPT conversation. Returns None if validation fails."""
    defect_data = validate_json(json_path)
    if defect_data is None:
        return None

    # Check image exists
    if not img_path.exists():
        print(f"  [WARN] Image not found: {img_path}")
        return None

    # Relative to project root so dataset is machine-independent
    rel_img = img_path.relative_to(PROJECT_ROOT)

    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"<image>{USER_PROMPT}"},
            {"role": "assistant", "content": json.dumps(defect_data, ensure_ascii=False)},
        ],
        "images": [str(rel_img)],
    }


def process_split(categories: list[str], split: str) -> list[dict]:
    """Process one split (train or eval) across all categories."""
    dataset = []
    stats = {"total": 0, "valid": 0, "skipped_img": 0, "skipped_json": 0}

    for category in categories:
        split_dir = SPLIT_DIR / category / split
        if not split_dir.exists():
            print(f"  [SKIP] {split_dir}")
            continue

        cat_count = 0
        for json_path in sorted(split_dir.glob("*.json")):
            stats["total"] += 1

            # Find corresponding image (png or jpg)
            img_path = json_path.with_suffix(".png")
            if not img_path.exists():
                img_path = json_path.with_suffix(".jpg")
            if not img_path.exists():
                stats["skipped_img"] += 1
                continue

            conv = build_conversation(img_path, json_path, split_dir)
            if conv is None:
                stats["skipped_json"] += 1
                continue

            dataset.append(conv)
            cat_count += 1
            stats["valid"] += 1

        print(f"  {category:12s}  {split:5s}  {cat_count:3d} samples")

    return dataset


def write_dataset_info(train_file: Path, eval_file: Path) -> None:
    """Generate dataset_info.json for LLaMA-Factory --dataset_dir."""
    train_rel = train_file.relative_to(OUTPUT_DIR)
    eval_rel = eval_file.relative_to(OUTPUT_DIR)

    common_tags = {
        "role_tag": "role",
        "content_tag": "content",
        "user_tag": "user",
        "assistant_tag": "assistant",
        "system_tag": "system",
    }

    info = {
        "industrial_vision_train": {
            "file_name": str(train_rel),
            "formatting": "sharegpt",
            "columns": {"messages": "messages", "images": "images"},
            "tags": common_tags,
        },
        "industrial_vision_eval": {
            "file_name": str(eval_rel),
            "formatting": "sharegpt",
            "columns": {"messages": "messages", "images": "images"},
            "tags": common_tags,
        },
    }

    info_path = OUTPUT_DIR / "dataset_info.json"
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    print(f"  Registry: {info_path}")


def write_readme() -> None:
    readme = OUTPUT_DIR / "README.md"
    readme.write_text(
        "# LoRA Training Dataset\n\n"
        "## Files\n\n"
        "- `industrial_vision_train.json` — ShareGPT format training data\n"
        "- `industrial_vision_eval.json` — ShareGPT format evaluation data\n"
        "- `dataset_info.json` — LLaMA-Factory dataset registry\n"
        "- `lora_split/` — per-image PNG + JSON annotations\n\n"
        "## Usage\n\n"
        "Run from **project root** with `--dataset_dir`:\n\n"
        "```bash\n"
        "cd vlm-sam-industrial-vision-v2\n\n"
        "llamafactory-cli train \\\n"
        "    --dataset_dir datasets/ \\\n"
        "    --dataset industrial_vision_train \\\n"
        "    --model_name_or_path models/qwen3vl_models/base/ \\\n"
        "    --template qwen3_vl \\\n"
        "    --finetuning_type lora \\\n"
        "    --lora_rank 16 \\\n"
        "    --output_dir outputs/lora_vlm \\\n"
        "    --per_device_train_batch_size 1 \\\n"
        "    --gradient_accumulation_steps 8 \\\n"
        "    --num_train_epochs 5 \\\n"
        "    --learning_rate 1e-4 \\\n"
        "    --fp16\n"
        "```\n\n"
        "Image paths are relative to project root, so CWD must be the project root.\n",
        encoding="utf-8",
    )
    print(f"  README:   {readme}")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Convert JSON annotations to LLaMA-Factory ShareGPT format"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without writing output files")
    parser.add_argument("--allow-empty-eval", action="store_true",
                        help="Allow eval split to have 0 samples (debug only)")
    args = parser.parse_args()

    categories = discover_categories()
    print(f"Categories ({len(categories)}): {categories}")
    print(f"Source: {SPLIT_DIR}\n")

    # Process train split
    print("Processing train split:")
    train_data = process_split(categories, "train")
    print(f"\n  Train total: {len(train_data)} valid samples\n")

    # Process eval split
    print("Processing eval split:")
    eval_data = process_split(categories, "eval")
    print(f"\n  Eval total: {len(eval_data)} valid samples\n")

    if args.dry_run:
        print("\n--- Dry-run summary ---")
        print(f"  Train: {len(train_data)} samples")
        print(f"  Eval:  {len(eval_data)} samples")
        if len(train_data) == 0:
            print("  [ERROR] Train split has 0 samples! Run mvtec_mask_to_json.py first.")
        if len(eval_data) == 0:
            msg = "  [ERROR] Eval split has 0 samples! Run mvtec_mask_to_json.py first."
            if not args.allow_empty_eval:
                print(msg)
                print("  Aborting. Use --allow-empty-eval to override (debug only).")
                sys.exit(1)
            else:
                print(msg)
                print("  [WARN] --allow-empty-eval specified, continuing anyway.")
        print("Dry run complete. No files written.")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    train_file = OUTPUT_DIR / "industrial_vision_train.json"
    eval_file = OUTPUT_DIR / "industrial_vision_eval.json"

    with open(train_file, "w", encoding="utf-8") as f:
        json.dump(train_data, f, ensure_ascii=False, indent=2)
    with open(eval_file, "w", encoding="utf-8") as f:
        json.dump(eval_data, f, ensure_ascii=False, indent=2)

    write_dataset_info(train_file, eval_file)
    write_readme()

    print(f"\nDone. train={len(train_data)}, eval={len(eval_data)}")
    print(f"  {train_file}")
    print(f"  {eval_file}")


if __name__ == "__main__":
    main()
