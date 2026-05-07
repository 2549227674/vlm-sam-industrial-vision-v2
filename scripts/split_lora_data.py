#!/usr/bin/env python3
"""Split MVTec AD defect images into train/eval for LoRA fine-tuning.

Reads:  simulator/mvtec/{metal_nut,screw,pill}/test/ (excludes good/)
Writes: datasets/lora_split/{category}/train/  (70%)
        datasets/lora_split/{category}/eval/   (30%)

Images are copied (not moved), with defect-type prefix to avoid filename
collisions (e.g. 000.png -> scratch_000.png). Fixed random.seed(42).

Usage:
    python scripts/split_lora_data.py
"""

import random
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_BASE = PROJECT_ROOT / "simulator" / "mvtec"
DST_BASE = PROJECT_ROOT / "datasets" / "lora_split"
CATEGORIES = ["metal_nut", "screw", "pill"]
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
SPLIT_RATIO = 0.7


def copy_files(file_list: list[Path], target_dir: Path, prefix: str) -> int:
    """Copy files to target_dir with defect-type prefix to avoid name collisions."""
    for img in file_list:
        shutil.copy2(img, target_dir / f"{prefix}_{img.name}")
    return len(file_list)


def split_category(category: str) -> tuple[int, int]:
    cat_src = SRC_BASE / category / "test"
    if not cat_src.exists():
        print(f"[SKIP] Not found: {cat_src}")
        return 0, 0

    train_dir = DST_BASE / category / "train"
    eval_dir = DST_BASE / category / "eval"

    # Clean rebuild to prevent data pollution across re-runs
    for d in (train_dir, eval_dir):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)

    cat_train = 0
    cat_eval = 0

    defect_types = sorted(
        d.name for d in cat_src.iterdir()
        if d.is_dir() and d.name != "good"
    )

    for defect in defect_types:
        images = sorted(
            f for f in (cat_src / defect).iterdir()
            if f.is_file() and f.suffix.lower() in IMAGE_SUFFIXES
        )
        random.shuffle(images)

        split_idx = int(len(images) * SPLIT_RATIO)
        cat_train += copy_files(images[:split_idx], train_dir, defect)
        cat_eval += copy_files(images[split_idx:], eval_dir, defect)

    # No-overlap safety check
    train_names = {f.name for f in train_dir.rglob("*") if f.is_file()}
    eval_names = {f.name for f in eval_dir.rglob("*") if f.is_file()}
    overlap = train_names & eval_names
    assert not overlap, f"Overlap detected between train and eval: {overlap}"

    return cat_train, cat_eval


def main() -> None:
    random.seed(42)

    print(f"Source: {SRC_BASE}")
    print(f"Target: {DST_BASE}")
    print(f"Split : {SPLIT_RATIO:.0%} train / {1 - SPLIT_RATIO:.0%} eval\n")

    total_train = 0
    total_eval = 0

    for category in CATEGORIES:
        n_train, n_eval = split_category(category)
        total_train += n_train
        total_eval += n_eval
        total = n_train + n_eval
        ratio = f"{n_train / total * 100:.0f}/{n_eval / total * 100:.0f}" if total else "N/A"
        print(f"  {category:12s}  train={n_train:3d}  eval={n_eval:3d}  total={total:3d}  ({ratio})")

    grand_total = total_train + total_eval
    print(f"\n{'─' * 50}")
    print(f"  Total  train={total_train}  eval={total_eval}  ({grand_total} images)")
    print("Done. No overlap detected.")


if __name__ == "__main__":
    main()
