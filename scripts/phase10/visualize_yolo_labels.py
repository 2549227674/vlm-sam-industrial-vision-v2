#!/usr/bin/env python3
"""Visualize YOLO labels overlaid on original images for QA.

Reads:  datasets/phase10/images/{split}/*.png
        datasets/phase10/labels/{split}/*.txt
        configs/phase10_classes.yaml
Writes: datasets/phase10/qa_viz/{split}/*.png  (image + bbox + mask overlay)

Usage:
    python scripts/phase10/visualize_yolo_labels.py
    python scripts/phase10/visualize_yolo_labels.py --split val --limit 20
    python scripts/phase10/visualize_yolo_labels.py --split train --with-mask
"""

import argparse
from pathlib import Path

import cv2
import numpy as np
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PHASE10_DIR = PROJECT_ROOT / "datasets" / "phase10"
MVTEC_DIR = PROJECT_ROOT / "simulator" / "mvtec"
CLASSES_FILE = PROJECT_ROOT / "configs" / "phase10_classes.yaml"

# Colors per category (BGR)
CATEGORY_COLORS = {
    "metal_nut": (255, 128, 0),   # cyan
    "cable": (0, 200, 255),       # orange
}

DEFAULT_COLOR = (0, 255, 0)  # green


def load_class_names(classes_path: Path) -> dict[int, str]:
    with open(classes_path) as f:
        data = yaml.safe_load(f)
    return {int(k): v for k, v in data["names"].items()}


def xywh_center_to_xyxy(cx: float, cy: float, w: float, h: float, img_w: int, img_h: int) -> tuple[int, int, int, int]:
    """Convert YOLO center-xywh normalized to pixel xyxy."""
    x1 = int((cx - w / 2) * img_w)
    y1 = int((cy - h / 2) * img_h)
    x2 = int((cx + w / 2) * img_w)
    y2 = int((cy + h / 2) * img_h)
    return max(0, x1), max(0, y1), min(img_w, x2), min(img_h, y2)


def find_mask_path(stem: str) -> Path | None:
    """Derive MVTec GT mask path from flat stem (category_defect_type_id)."""
    parts = stem.split("_", 1)
    if len(parts) < 2:
        return None
    category = parts[0]
    rest = parts[1]
    # rest is defect_type_id, e.g. "bent_000" or "cut_outer_insulation_000"
    # Split from the right to get id
    rest_parts = rest.rsplit("_", 1)
    if len(rest_parts) < 2:
        return None
    defect_type = rest_parts[0]
    img_id = rest_parts[1]
    mask_path = MVTEC_DIR / category / "ground_truth" / defect_type / f"{img_id}_mask.png"
    if mask_path.exists():
        return mask_path
    return None


def draw_bbox_overlay(
    img: np.ndarray,
    label_path: Path,
    class_names: dict[int, str],
    with_mask: bool = False,
) -> np.ndarray:
    """Draw YOLO bboxes on image. Returns annotated copy."""
    vis = img.copy()
    img_h, img_w = img.shape[:2]

    with open(label_path) as f:
        lines = f.readlines()

    for line in lines:
        parts = line.strip().split()
        if len(parts) < 5:
            continue
        class_id = int(parts[0])
        cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])

        x1, y1, x2, y2 = xywh_center_to_xyxy(cx, cy, w, h, img_w, img_h)

        # Color by category
        class_name = class_names.get(class_id, f"cls_{class_id}")
        category = class_name.split("/")[0] if "/" in class_name else ""
        color = CATEGORY_COLORS.get(category, DEFAULT_COLOR)

        # Draw bbox
        cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)

        # Label
        label = f"{class_name} ({class_id})"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
        cv2.rectangle(vis, (x1, y1 - th - 4), (x1 + tw + 2, y1), color, -1)
        cv2.putText(vis, label, (x1 + 1, y1 - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    # Overlay GT mask if requested
    if with_mask:
        stem = label_path.stem
        mask_path = find_mask_path(stem)
        if mask_path and mask_path.exists():
            mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            if mask is not None:
                _, binary = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
                # Create red overlay for mask
                overlay = vis.copy()
                overlay[binary > 0] = (0, 0, 255)  # red
                vis = cv2.addWeighted(vis, 0.7, overlay, 0.3, 0)

    return vis


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Visualize YOLO labels for QA"
    )
    parser.add_argument("--split", default="val", choices=["train", "val", "all"],
                        help="Which split to visualize (default: val)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max images to process (0 = all)")
    parser.add_argument("--with-mask", action="store_true",
                        help="Overlay GT mask on visualization")
    args = parser.parse_args()

    class_names = load_class_names(CLASSES_FILE)

    images_dir = PHASE10_DIR / "images" / args.split
    labels_dir = PHASE10_DIR / "labels" / args.split
    output_dir = PHASE10_DIR / "qa_viz" / args.split
    output_dir.mkdir(parents=True, exist_ok=True)

    if not images_dir.exists():
        print(f"ERROR: {images_dir} not found. Run split_mvtec_localization.py first.")
        return

    image_files = sorted(images_dir.glob("*.png"))
    if args.limit > 0:
        image_files = image_files[:args.limit]

    print(f"Processing {len(image_files)} images from {args.split} split...")
    print(f"Output: {output_dir}")

    processed = 0
    skipped = 0

    for img_path in image_files:
        label_path = labels_dir / f"{img_path.stem}.txt"
        if not label_path.exists():
            skipped += 1
            continue

        img = cv2.imread(str(img_path))
        if img is None:
            skipped += 1
            continue

        vis = draw_bbox_overlay(img, label_path, class_names, with_mask=args.with_mask)
        out_path = output_dir / img_path.name
        cv2.imwrite(str(out_path), vis)
        processed += 1

    print(f"Done. {processed} visualizations written, {skipped} skipped.")
    print(f"Open {output_dir} to review.")


if __name__ == "__main__":
    main()
