#!/usr/bin/env python3
"""Split Phase 10 YOLO labels into train/val sets (stratified by class).

Reads:  datasets/phase10/labels/all/*.txt  (output of mvtec_mask_to_yolo.py)
        datasets/phase10/images/all/*.png
Writes: datasets/phase10/labels/{train,val}/*.txt
        datasets/phase10/images/{train,val}/*.png
        datasets/phase10/phase10.yaml       (YOLO dataset config)
        datasets/phase10/splits.json        (reproducible split manifest)

Split strategy: 70/30 stratified by dominant class per image.
Uses random seed for reproducibility.

Usage:
    python scripts/phase10/split_mvtec_localization.py
    python scripts/phase10/split_mvtec_localization.py --seed 42 --ratio 0.7
"""

import argparse
import json
import random
import shutil
from collections import defaultdict
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PHASE10_DIR = PROJECT_ROOT / "datasets" / "phase10"
CLASSES_FILE = PROJECT_ROOT / "configs" / "phase10_classes.yaml"

DEFAULT_SEED = 42
DEFAULT_TRAIN_RATIO = 0.7


def load_class_names(classes_path: Path) -> dict[int, str]:
    """Load {class_id: name} from YAML."""
    with open(classes_path) as f:
        data = yaml.safe_load(f)
    return {int(k): v for k, v in data["names"].items()}


def get_dominant_class(label_path: Path) -> int:
    """Return the class_id with most bboxes in a label file."""
    class_counts: dict[int, int] = defaultdict(int)
    with open(label_path) as f:
        for line in f:
            parts = line.strip().split()
            if parts:
                class_counts[int(parts[0])] += 1
    if not class_counts:
        return -1
    return max(class_counts, key=class_counts.get)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split Phase 10 YOLO data into train/val"
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help=f"Random seed (default: {DEFAULT_SEED})")
    parser.add_argument("--ratio", type=float, default=DEFAULT_TRAIN_RATIO,
                        help=f"Train ratio (default: {DEFAULT_TRAIN_RATIO})")
    args = parser.parse_args()

    labels_all = PHASE10_DIR / "labels" / "all"
    images_all = PHASE10_DIR / "images" / "all"

    if not labels_all.exists():
        print(f"ERROR: {labels_all} not found. Run mvtec_mask_to_yolo.py first.")
        return

    class_names = load_class_names(CLASSES_FILE)

    # Group images by dominant class
    class_files: dict[int, list[str]] = defaultdict(list)
    for label_path in sorted(labels_all.glob("*.txt")):
        stem = label_path.stem
        dom_class = get_dominant_class(label_path)
        if dom_class >= 0:
            class_files[dom_class].append(stem)

    # Stratified split
    rng = random.Random(args.seed)
    train_stems: list[str] = []
    val_stems: list[str] = []

    print(f"{'Class':4s}  {'Name':35s}  {'Total':>5s}  {'Train':>5s}  {'Val':>5s}")
    print(f"{'-'*4}  {'-'*35}  {'-'*5}  {'-'*5}  {'-'*5}")

    for class_id in sorted(class_files.keys()):
        files = class_files[class_id]
        rng.shuffle(files)
        n_train = max(1, int(len(files) * args.ratio))
        train_stems.extend(files[:n_train])
        val_stems.extend(files[n_train:])
        name = class_names.get(class_id, f"unknown_{class_id}")
        print(f"{class_id:4d}  {name:35s}  {len(files):5d}  {n_train:5d}  {len(files) - n_train:5d}")

    # Shuffle final lists
    rng.shuffle(train_stems)
    rng.shuffle(val_stems)

    # Create output directories
    for split in ["train", "val"]:
        (PHASE10_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)
        (PHASE10_DIR / "images" / split).mkdir(parents=True, exist_ok=True)

    # Copy files
    split_manifest = {"seed": args.seed, "ratio": args.ratio, "train": [], "val": []}

    for split, stems in [("train", train_stems), ("val", val_stems)]:
        for stem in stems:
            label_src = labels_all / f"{stem}.txt"
            img_src = images_all / f"{stem}.png"
            label_dst = PHASE10_DIR / "labels" / split / f"{stem}.txt"
            img_dst = PHASE10_DIR / "images" / split / f"{stem}.png"

            if label_src.exists():
                shutil.copy2(label_src, label_dst)
            if img_src.exists():
                shutil.copy2(img_src, img_dst)

            split_manifest[split].append(stem)

    # Write split manifest
    manifest_path = PHASE10_DIR / "splits.json"
    with open(manifest_path, "w") as f:
        json.dump(split_manifest, f, indent=2)

    # Write YOLO dataset config
    dataset_yaml = {
        "path": str(PHASE10_DIR),
        "train": "images/train",
        "val": "images/val",
        "names": {int(k): v for k, v in class_names.items()},
    }
    yaml_path = PHASE10_DIR / "phase10.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(dataset_yaml, f, default_flow_style=False, sort_keys=False)

    print(f"\nDone. Train: {len(train_stems)}, Val: {len(val_stems)}")
    print(f"Manifest: {manifest_path}")
    print(f"YOLO config: {yaml_path}")


if __name__ == "__main__":
    main()
