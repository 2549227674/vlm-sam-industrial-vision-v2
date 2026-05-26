#!/usr/bin/env python3
"""Convert MVTec AD ground-truth masks to YOLO detection labels.

Reads:  simulator/mvtec/{category}/ground_truth/{defect_type}/*_mask.png
Writes: datasets/phase10/labels/{split}/{category}_{defect_type}_{id}.txt

Each label file contains one line per connected component:
    <class_id> <cx> <cY> <w> <h>    (center-xywh, normalized to [0,1])

Coordinate convention:
    - YOLO label files: center-xywh normalized  (cx, cy, w, h)
    - API payload:       top-left-xywh normalized (x, y, w, h)
    This script outputs YOLO format only.

Usage:
    python scripts/phase10/mvtec_mask_to_yolo.py
    python scripts/phase10/mvtec_mask_to_yolo.py --dry-run
    python scripts/phase10/mvtec_mask_to_yolo.py --categories metal_nut
"""

import argparse
from pathlib import Path

import cv2
import numpy as np
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MVTEC_DIR = PROJECT_ROOT / "simulator" / "mvtec"
OUTPUT_DIR = PROJECT_ROOT / "datasets" / "phase10"
CLASSES_FILE = PROJECT_ROOT / "configs" / "phase10_classes.yaml"

# Phase 10 v1 scope: metal_nut + cable
CATEGORIES = ["metal_nut", "cable"]

# Filter: minimum component area in pixels (drop annotation noise)
MIN_COMPONENT_AREA_PX = 16

# Padding: applied to each bbox before normalization
# max(PAD_MIN_PX, PAD_RATIO * max(w, h))
PAD_MIN_PX = 3
PAD_RATIO = 0.02

# Max bboxes per image (API v1.2 limit)
MAX_BBOXES_PER_IMAGE = 16


def load_class_map(classes_path: Path) -> dict[str, int]:
    """Load {category/defect_type: class_id} from YAML."""
    with open(classes_path) as f:
        data = yaml.safe_load(f)
    return {v: k for k, v in data["names"].items()}


def xywh_center_to_xyxy(cx: float, cy: float, w: float, h: float) -> tuple[float, float, float, float]:
    """Convert center-xywh to corner-xyxy."""
    x1 = cx - w / 2
    y1 = cy - h / 2
    x2 = cx + w / 2
    y2 = cy + h / 2
    return x1, y1, x2, y2


def xyxy_to_xywh_center(x1: float, y1: float, x2: float, y2: float) -> tuple[float, float, float, float]:
    """Convert corner-xyxy to center-xywh."""
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    w = x2 - x1
    h = y2 - y1
    return cx, cy, w, h


def process_mask(
    mask_path: Path,
    img_w: int,
    img_h: int,
) -> list[tuple[float, float, float, float]]:
    """Extract YOLO center-xywh normalized bboxes from a binary mask.

    Returns list of (cx, cy, w, h) in [0,1] range.
    """
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return []

    # Binary threshold: mask pixels are 0 or 255
    _, binary = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)

    # Find connected components (8-connected)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        binary, connectivity=8
    )

    bboxes = []
    # Skip label 0 (background)
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < MIN_COMPONENT_AREA_PX:
            continue

        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        w = stats[i, cv2.CC_STAT_WIDTH]
        h = stats[i, cv2.CC_STAT_HEIGHT]

        # Apply padding
        pad = max(PAD_MIN_PX, int(PAD_RATIO * max(w, h)))
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(img_w, x + w + pad)
        y2 = min(img_h, y + h + pad)

        # Convert to center-xywh normalized
        cx, cy, nw, nh = xyxy_to_xywh_center(
            x1 / img_w, y1 / img_h, x2 / img_w, y2 / img_h
        )

        # Clamp to [0, 1]
        cx = max(0.0, min(1.0, cx))
        cy = max(0.0, min(1.0, cy))
        nw = max(0.0, min(1.0, nw))
        nh = max(0.0, min(1.0, nh))

        if nw > 0 and nh > 0:
            bboxes.append((cx, cy, nw, nh))

    # Limit to MAX_BBOXES_PER_IMAGE (keep largest)
    if len(bboxes) > MAX_BBOXES_PER_IMAGE:
        bboxes.sort(key=lambda b: b[2] * b[3], reverse=True)
        bboxes = bboxes[:MAX_BBOXES_PER_IMAGE]

    return bboxes


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert MVTec GT masks to YOLO detection labels"
    )
    parser.add_argument(
        "--categories", nargs="+", default=CATEGORIES,
        help="Categories to process (default: metal_nut cable)"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without writing files")
    args = parser.parse_args()

    class_map = load_class_map(CLASSES_FILE)

    # Output directories
    labels_dir = OUTPUT_DIR / "labels" / "all"  # flat before split
    images_dir = OUTPUT_DIR / "images" / "all"
    if not args.dry_run:
        labels_dir.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)

    total_images = 0
    total_bboxes = 0
    total_filtered = 0
    stats: dict[str, dict[str, int]] = {}

    print(f"{'Category':12s}  {'Defect Type':25s}  {'Images':>6s}  {'BBoxes':>6s}  {'Filtered':>8s}")
    print(f"{'-'*12}  {'-'*25}  {'-'*6}  {'-'*6}  {'-'*8}")

    for category in args.categories:
        gt_dir = MVTEC_DIR / category / "ground_truth"
        test_dir = MVTEC_DIR / category / "test"
        if not gt_dir.exists():
            print(f"  [SKIP] {gt_dir} not found")
            continue

        stats[category] = {}

        for defect_type_dir in sorted(gt_dir.iterdir()):
            if not defect_type_dir.is_dir():
                continue
            defect_type = defect_type_dir.name
            class_key = f"{category}/{defect_type}"

            if class_key not in class_map:
                print(f"  [SKIP] {class_key} not in class map")
                continue

            class_id = class_map[class_key]
            img_count = 0
            bbox_count = 0
            filtered_count = 0

            for mask_path in sorted(defect_type_dir.glob("*_mask.png")):
                # Derive image path from mask path
                img_id = mask_path.stem.replace("_mask", "")
                img_path = test_dir / defect_type / f"{img_id}.png"

                if not img_path.exists():
                    filtered_count += 1
                    continue

                # Read image dimensions
                img = cv2.imread(str(img_path))
                if img is None:
                    filtered_count += 1
                    continue
                img_h, img_w = img.shape[:2]

                # Process mask
                bboxes = process_mask(mask_path, img_w, img_h)

                if not bboxes:
                    filtered_count += 1
                    continue

                # Write label file
                label_name = f"{category}_{defect_type}_{img_id}.txt"
                label_path = labels_dir / label_name

                if not args.dry_run:
                    # Copy image to flat directory
                    dst_img = images_dir / f"{category}_{defect_type}_{img_id}.png"
                    if not dst_img.exists():
                        import shutil
                        shutil.copy2(img_path, dst_img)

                    with open(label_path, "w") as f:
                        for cx, cy, w, h in bboxes:
                            f.write(f"{class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")

                img_count += 1
                bbox_count += len(bboxes)

            stats[category][defect_type] = img_count
            total_images += img_count
            total_bboxes += bbox_count
            total_filtered += filtered_count

            print(f"  {category:12s}  {defect_type:25s}  {img_count:6d}  {bbox_count:6d}  {filtered_count:8d}")

    # Summary
    mode = "DRY-RUN" if args.dry_run else "Done"
    print(f"\n{mode}. {total_images} images, {total_bboxes} bboxes, {total_filtered} filtered.")

    if not args.dry_run:
        print(f"Labels: {labels_dir}")
        print(f"Images: {images_dir}")


if __name__ == "__main__":
    main()
