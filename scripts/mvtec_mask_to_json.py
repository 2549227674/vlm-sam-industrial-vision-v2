#!/usr/bin/env python3
"""Generate LoRA training JSON annotations from MVTec ground-truth masks.

Reads:  datasets/lora_split/{category}/{train,eval}/*.png  (output of split_lora_data.py)
        simulator/mvtec/{category}/ground_truth/{defect_type}/{id}_mask.png
Writes: datasets/lora_split/{category}/{train,eval}/*.json  (one per image, same dir)

Each JSON follows DefectCreate schema (API_CONTRACT.md §2):
  - category, defect_type, severity, confidence, bboxes (≤16), description (中文)

Usage:
    python scripts/mvtec_mask_to_json.py
    python scripts/mvtec_mask_to_json.py --dry-run   # preview counts without writing
"""

import argparse
import json
from pathlib import Path

import cv2

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPLIT_DIR = PROJECT_ROOT / "datasets" / "lora_split"
MVTEC_DIR = PROJECT_ROOT / "simulator" / "mvtec"
# v1 初版 3 类：["metal_nut", "screw", "pill"]
# v2 重做 15 类
CATEGORIES = [
    "bottle", "cable", "capsule", "carpet", "grid", "hazelnut", "leather",
    "metal_nut", "pill", "screw", "tile", "toothbrush", "transistor",
    "wood", "zipper",
]

# 全 15 类缺陷类型中文映射（约 65-70 种）
DEFECT_CN = {
    # bottle
    "broken_large": "大面积破损",
    "broken_small": "小面积破损",
    "contamination": "污染",
    # cable
    "bent_wire": "弯曲导线",
    "cable_swap": "电缆错位",
    "combined": "复合缺陷",
    "cut_inner_insulation": "内部绝缘层切割",
    "cut_outer_insulation": "外部绝缘层切割",
    "missing_cable": "缺少电缆",
    "missing_wire": "缺少导线",
    "poke_insulation": "绝缘层刺穿",
    # capsule
    "crack": "裂纹",
    "faulty_imprint": "印刷缺陷",
    "scratch": "划痕",
    "squeeze": "挤压变形",
    # carpet
    "color": "色差",
    "cut": "切割缺陷",
    "hole": "孔洞",
    "metal_contamination": "金属污染",
    "thread": "线头缺陷",
    # grid
    "bent": "弯曲",
    "broken": "破损",
    "glue": "胶水残留",
    "metal_contamination": "金属污染",
    "thread": "线头缺陷",
    # hazelnut
    "crack": "裂纹",
    "hole": "孔洞",
    "cut": "切割缺陷",
    "print": "印刷缺陷",
    # leather
    "color": "色差",
    "cut": "切割缺陷",
    "fold": "折叠缺陷",
    "glue": "胶水残留",
    "poke": "刺穿缺陷",
    # metal_nut
    "bent": "弯曲",
    "color": "色差",
    "flip": "翻转",
    "scratch": "划痕",
    # pill
    "color": "色差",
    "combined": "复合缺陷",
    "contamination": "污染",
    "crack": "裂纹",
    "faulty_imprint": "印刷缺陷",
    "pill_type": "药片类型错误",
    "scratch": "划痕",
    # screw
    "manipulated_front": "前端异常",
    "scratch_head": "头部划痕",
    "scratch_neck": "颈部划痕",
    "thread_side": "侧面螺纹缺陷",
    "thread_top": "顶部螺纹缺陷",
    # tile
    "crack": "裂纹",
    "glue_strip": "胶带残留",
    "gray_stroke": "灰色笔触",
    "oil": "油污",
    "rough": "粗糙缺陷",
    # toothbrush
    "defective": "缺陷",
    # transistor
    "bent_lead": "引脚弯曲",
    "cut_lead": "引脚切割",
    "damaged_case": "外壳破损",
    "misplaced": "错位",
    # wood
    "color": "色差",
    "combined": "复合缺陷",
    "hole": "孔洞",
    "liquid": "液体残留",
    "scratch": "划痕",
    # zipper
    "broken_teeth": "齿断裂",
    "combined": "复合缺陷",
    "fabric_border": "织物边缘缺陷",
    "fabric_interior": "织物内部缺陷",
    "rough": "粗糙缺陷",
    "split_teeth": "齿分离",
    "squeezed_teeth": "齿挤压",
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
    parser = argparse.ArgumentParser(
        description="Generate LoRA JSON annotations from MVTec GT masks"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview counts without writing JSON files")
    args = parser.parse_args()

    splits = ["train", "eval"]
    grand_total = 0
    grand_skipped = 0

    print(f"{'Category':12s}  {'Split':5s}  {'Generated':>9s}  {'Skipped':>7s}")
    print(f"{'-'*12}  {'-'*5}  {'-'*9}  {'-'*7}")

    for category in CATEGORIES:
        mvtec_gt = MVTEC_DIR / category / "ground_truth"

        for split in splits:
            split_dir = SPLIT_DIR / category / split
            if not split_dir.exists():
                print(f"  [SKIP] {split_dir}")
                continue

            cat_count = 0
            skip_count = 0

            for img_path in sorted(split_dir.glob("*.png")):
                data = process_image(img_path, mvtec_gt)
                if data is None:
                    skip_count += 1
                    continue

                data["category"] = category
                json_path = img_path.with_suffix(".json")

                if not args.dry_run:
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

                cat_count += 1

            if skip_count > 0:
                print(f"  [WARN] {category}/{split}: {skip_count} images skipped (mask missing)")

            print(f"  {category:12s}  {split:5s}  {cat_count:9d}  {skip_count:7d}")
            grand_total += cat_count
            grand_skipped += skip_count

    mode = "DRY-RUN" if args.dry_run else "Done"
    print(f"\n{mode}. {grand_total} annotations, {grand_skipped} skipped.")
    if args.dry_run:
        print("  (No files were written)")


if __name__ == "__main__":
    main()
