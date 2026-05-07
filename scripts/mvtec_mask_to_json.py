#!/usr/bin/env python3
"""Generate LoRA training JSON annotations from MVTec ground-truth masks.

Reads:  datasets/lora_split/{category}/train/*.png  (output of split_lora_data.py)
        simulator/mvtec/{category}/ground_truth/{defect_type}/{id}_mask.png
Writes: datasets/lora_split/{category}/train/*.json  (one per image, same dir)

Each JSON follows DefectCreate schema (API_CONTRACT.md §2):
  - category, defect_type, severity, confidence, bboxes (≤16), description (中文)

Usage:
    python scripts/mvtec_mask_to_json.py
"""

import json
from pathlib import Path

import cv2

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPLIT_DIR = PROJECT_ROOT / "datasets" / "lora_split"
MVTEC_DIR = PROJECT_ROOT / "simulator" / "mvtec"
CATEGORIES = ["metal_nut", "screw", "pill"]

DEFECT_CN = {
    "bent": "弯曲",
    "color": "色差",
    "combined": "复合缺陷",
    "contamination": "污染",
    "crack": "裂纹",
    "damage": "破损",
    "flip": "翻转",
    "missing_hole": "缺孔",
    "scratch": "划痕",
}

MIN_CONTOUR_AREA = 5


def get_position_desc(x: float, y: float) -> str:
    """Nine-grid position: x/y in [0,1]."""
    v = "上" if y < 0.33 else "下" if y > 0.66 else "中"
    h = "左" if x < 0.33 else "右" if x > 0.66 else "中"
    if v == "中" and h == "中":
        return "正中央"
    return f"{h}{v}方"


def area_to_confidence(rel_area: float) -> float:
    """Larger defect area -> higher confidence. Capped at 0.99."""
    return round(min(0.99, 0.60 + (rel_area / 0.05) * 0.39), 2)


def area_to_severity(rel_area: float) -> str:
    if rel_area > 0.05:
        return "high"
    if rel_area > 0.01:
        return "medium"
    return "low"


def build_bboxes(mask: cv2.typing.MatLike) -> tuple[list[dict], float, str]:
    """Extract normalized bboxes from mask, return (bboxes, total_rel_area, primary_pos)."""
    img_h, img_w = mask.shape
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    bboxes = []
    total_area = 0
    max_area = 0
    primary_pos = "正中央"

    for c in contours:
        area = cv2.contourArea(c)
        if area < MIN_CONTOUR_AREA:
            continue

        x, y, w, h = cv2.boundingRect(c)
        nx, ny, nw, nh = x / img_w, y / img_h, w / img_w, h / img_h

        bboxes.append({
            "x": round(nx, 4),
            "y": round(ny, 4),
            "w": round(nw, 4),
            "h": round(nh, 4),
        })
        total_area += area

        if area > max_area:
            max_area = area
            primary_pos = get_position_desc(nx + nw / 2, ny + nh / 2)

    return bboxes[:16], total_area / (img_w * img_h), primary_pos


def build_description(defect_cn: str, n_bboxes: int, pos: str) -> str:
    if n_bboxes > 1:
        return f"检测到 {n_bboxes} 处{defect_cn}瑕疵，主要集中在{pos}。"
    return f"检测到{defect_cn}瑕疵，位于工件{pos}区域。"


def process_image(img_path: Path, mvtec_gt: Path) -> dict | None:
    """Process one image: parse filename, find mask, build JSON dict."""
    parts = img_path.stem.split("_")
    defect_type = "_".join(parts[:-1])
    img_id = parts[-1]

    mask_path = mvtec_gt / defect_type / f"{img_id}_mask.png"
    if not mask_path.exists():
        print(f"  [WARN] mask not found: {mask_path}")
        return None

    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return None

    bboxes, rel_area, primary_pos = build_bboxes(mask)
    defect_cn = DEFECT_CN.get(defect_type, defect_type)

    return {
        "category": "",       # filled by caller
        "defect_type": defect_type,
        "severity": area_to_severity(rel_area),
        "confidence": area_to_confidence(rel_area),
        "bboxes": bboxes,
        "description": build_description(defect_cn, len(bboxes), primary_pos),
    }


def main() -> None:
    total = 0

    for category in CATEGORIES:
        train_dir = SPLIT_DIR / category / "train"
        if not train_dir.exists():
            print(f"[SKIP] {train_dir}")
            continue

        mvtec_gt = MVTEC_DIR / category / "ground_truth"
        cat_count = 0

        for img_path in sorted(train_dir.glob("*.png")):
            data = process_image(img_path, mvtec_gt)
            if data is None:
                continue

            data["category"] = category
            json_path = img_path.with_suffix(".json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            cat_count += 1

        print(f"  {category:12s}  {cat_count:3d} JSONs generated")
        total += cat_count

    print(f"\nDone. {total} annotations saved to {SPLIT_DIR}")


if __name__ == "__main__":
    main()
