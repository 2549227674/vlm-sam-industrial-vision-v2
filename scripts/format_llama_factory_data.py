#!/usr/bin/env python3
"""Convert per-image JSON annotations to LLaMA-Factory ShareGPT multimodal format.

Reads:  datasets/lora_split/{category}/train/*.png + *.json
Writes: datasets/industrial_vision_train.json  (ShareGPT format)
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
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPLIT_DIR = PROJECT_ROOT / "datasets" / "lora_split"
OUTPUT_DIR = PROJECT_ROOT / "datasets"
CATEGORIES = ["metal_nut", "screw", "pill"]

SYSTEM_PROMPT = "你是一个工业视觉质检专家。"
USER_PROMPT = (
    "请仔细观察这张图片，检测其中是否存在缺陷。"
    "如果存在，请严格输出包含 category, defect_type, severity, "
    "confidence, bboxes 和 description 的 JSON 报告。"
)


def build_conversation(img_path: Path, json_path: Path) -> dict:
    with open(json_path, encoding="utf-8") as f:
        defect_data = json.load(f)

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


def write_dataset_info(data_file: Path) -> None:
    """Generate dataset_info.json for LLaMA-Factory --dataset_dir."""
    # file_name relative to dataset_dir (= OUTPUT_DIR)
    rel_name = data_file.relative_to(OUTPUT_DIR)
    info = {
        "industrial_vision": {
            "file_name": str(rel_name),
            "formatting": "sharegpt",
            "columns": {"messages": "messages", "images": "images"},
            "tags": {
                "role_tag": "role",
                "content_tag": "content",
                "user_tag": "user",
                "assistant_tag": "assistant",
            },
        }
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
        "- `dataset_info.json` — LLaMA-Factory dataset registry\n"
        "- `lora_split/` — per-image PNG + JSON annotations\n\n"
        "## Usage\n\n"
        "Run from **project root** with `--dataset_dir`:\n\n"
        "```bash\n"
        "cd vlm-sam-industrial-vision-v2\n\n"
        "llamafactory-cli train \\\n"
        "    --dataset_dir datasets/ \\\n"
        "    --dataset industrial_vision \\\n"
        "    --model_name_or_path models/qwen3vl_models/base/ \\\n"
        "    --template qwen2_vl \\\n"
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
    dataset = []

    for category in CATEGORIES:
        train_dir = SPLIT_DIR / category / "train"
        if not train_dir.exists():
            print(f"[SKIP] {train_dir}")
            continue

        for json_path in sorted(train_dir.glob("*.json")):
            img_path = json_path.with_suffix(".png")
            if not img_path.exists():
                img_path = json_path.with_suffix(".jpg")
            if not img_path.exists():
                continue

            dataset.append(build_conversation(img_path, json_path))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data_file = OUTPUT_DIR / "industrial_vision_train.json"
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    write_dataset_info(data_file)
    write_readme()

    print(f"\nDone. {len(dataset)} conversations -> {data_file}")


if __name__ == "__main__":
    main()
