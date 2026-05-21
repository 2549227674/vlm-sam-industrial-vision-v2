#!/usr/bin/env python3
"""Evaluate EfficientAD raw scores on MVTec test set using RKNNLite on board.

Runs model.rknn (FP16/no-quant raw EfficientAD) on all test images and computes
five candidate metrics identical to ead_worker.cpp:

  raw_score   — ReduceMax output (model internal)
  map_max     — max pixel in raw anomaly map
  map_mean    — mean of entire raw anomaly map
  map_top1    — mean of top-1% pixels
  map_top01   — mean of top-0.1% pixels

final_score is selected by --score-mode (default: map_mean).

Designed to run on Orange Pi aarch64 with rknn_toolkit_lite2 installed.
Does NOT run FastSAM, Qwen3-VL, or upload — only EfficientAD.

Usage:
    python3 evaluate_efficientad_rknn_on_board.py \\
        --mvtec-root /home/orangepi/vlm-sam-industrial-vision-v2/simulator/mvtec \\
        --model-root /home/orangepi/models/efficientad_models \\
        --output-csv results/phase8_threshold_calibration/rknn_scores_15cls.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# MVTec AD full 15 classes
CATEGORIES = [
    "bottle", "cable", "capsule", "carpet", "grid",
    "hazelnut", "leather", "metal_nut", "pill", "screw",
    "tile", "toothbrush", "transistor", "wood", "zipper",
]

INPUT_SIZE = 256
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp"}

# Score mode string to index mapping (matches common::ScoreMode enum)
SCORE_MODES = ["raw_score", "map_max", "map_mean", "map_top1", "map_top01"]


def check_dependencies():
    """Check that required packages are available."""
    try:
        from rknnlite.api import RKNNLite  # noqa: F401
    except ImportError:
        print("ERROR: rknnlite not found. Install rknn_toolkit_lite2 on the board.")
        print("  pip install rknn_toolkit_lite2-2.3.2-cp3XX-...-aarch64.whl")
        sys.exit(1)
    try:
        import cv2  # noqa: F401
    except ImportError:
        print("ERROR: opencv-python not found. Install with: pip install opencv-python-headless")
        sys.exit(1)


def preprocess_image(img_path: str) -> np.ndarray | None:
    """Load and preprocess image to uint8 NHWC RGB for RKNN input.

    Matches ead_worker.cpp: decode -> resize to 256x256 -> pass as uint8.
    Returns shape (1, 256, 256, 3) uint8, or None on failure.
    """
    img = cv2.imread(img_path, cv2.IMREAD_COLOR)
    if img is None:
        return None
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    if img.shape[0] != INPUT_SIZE or img.shape[1] != INPUT_SIZE:
        img = cv2.resize(img, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_LINEAR)
    return img[np.newaxis]  # (1, 256, 256, 3)


def compute_metrics(raw_score_arr: np.ndarray,
                    anomaly_map_arr: np.ndarray) -> dict[str, float]:
    """Compute five metrics from raw EfficientAD outputs.

    Logic matches ead_worker.cpp exactly:
    - raw_score: scalar from model output
    - map_max: max of anomaly_map
    - map_mean: mean of anomaly_map (this is final_score when score_mode=map_mean)
    - map_top1: mean of top-1% pixels
    - map_top01: mean of top-0.1% pixels
    """
    # raw_score: extract scalar
    score_val = float(raw_score_arr.flatten()[0])

    # anomaly_map: flatten to 1D
    flat = anomaly_map_arr.astype(np.float32).flatten()
    n_pixels = len(flat)

    map_max_val = float(np.max(flat))
    map_mean_val = float(np.mean(flat))

    # top-k mean (matches C++ top_k_mean)
    top1_k = max(1, n_pixels // 100)
    top01_k = max(1, n_pixels // 1000)

    sorted_desc = np.sort(flat)[::-1]
    map_top1_val = float(np.mean(sorted_desc[:top1_k]))
    map_top01_val = float(np.mean(sorted_desc[:top01_k]))

    return {
        "raw_score": score_val,
        "map_max": map_max_val,
        "map_mean": map_mean_val,
        "map_top1": map_top1_val,
        "map_top01": map_top01_val,
    }


def evaluate_category(
    category: str,
    mvtec_root: Path,
    model_root: Path,
    score_mode: str,
    csv_writer: csv.DictWriter | None = None,
) -> tuple[int, int, int]:
    """Evaluate one category on board using RKNNLite.

    Returns (good_count, defect_count, failed_count).
    """
    from rknnlite.api import RKNNLite

    model_path = model_root / category / "model.rknn"
    test_dir = mvtec_root / category / "test"

    if not model_path.exists():
        print(f"  [SKIP] model not found: {model_path}")
        return 0, 0, 0
    if not test_dir.exists():
        print(f"  [SKIP] test dir not found: {test_dir}")
        return 0, 0, 0

    # Load RKNN model
    rknn = RKNNLite(verbose=False)
    ret = rknn.load_rknn(str(model_path))
    if ret != 0:
        print(f"  [ERROR] load_rknn failed for '{category}': {ret}")
        return 0, 0, 0

    ret = rknn.init_runtime()
    if ret != 0:
        print(f"  [ERROR] init_runtime failed for '{category}': {ret}")
        rknn.release()
        return 0, 0, 0

    good_count = 0
    defect_count = 0
    failed_count = 0

    # Count total images
    total_images = 0
    for sub_dir in sorted(test_dir.iterdir()):
        if sub_dir.is_dir():
            total_images += sum(
                1 for p in sub_dir.iterdir()
                if p.suffix.lower() in IMAGE_EXTENSIONS
            )

    processed = 0
    t_start = time.perf_counter()

    for sub_dir in sorted(test_dir.iterdir()):
        if not sub_dir.is_dir():
            continue
        sub_name = sub_dir.name
        is_good = (sub_name == "good")

        images = sorted(
            p for p in sub_dir.iterdir()
            if p.suffix.lower() in IMAGE_EXTENSIONS
        )
        if not images:
            continue

        for img_path in images:
            # Preprocess
            inp = preprocess_image(str(img_path))
            if inp is None:
                print(f"  WARN: cannot read {img_path}")
                failed_count += 1
                total_images = max(0, total_images - 1)
                continue

            # Run inference using RKNNLite API: rknn.inference(inputs=[...])
            # Returns list of numpy arrays, one per output tensor.
            try:
                outputs = rknn.inference(inputs=[inp])
            except Exception as e:
                print(f"  WARN: inference failed for {img_path.name}: {e}")
                failed_count += 1
                continue

            if outputs is None or len(outputs) == 0:
                print(f"  WARN: empty outputs for {img_path.name}")
                failed_count += 1
                continue

            # Locate raw_score and raw_anomaly_map by positional index.
            # Model outputs: [anomaly_map, pred_score] or [raw_anomaly_map, raw_score].
            # Score output has fewer elements (scalar or tiny), map has many (256x256=65536).
            # C++ fallback: smallest n_elems = score, largest n_elems = map.
            score_arr = None
            map_arr = None

            if len(outputs) >= 2:
                # Find by element count (matches C++ positional fallback)
                min_elems = float('inf')
                max_elems = 0
                min_idx = 0
                max_idx = 0
                for i, out_data in enumerate(outputs):
                    n = out_data.size
                    if n < min_elems:
                        min_elems = n
                        min_idx = i
                    if n > max_elems:
                        max_elems = n
                        max_idx = i
                score_arr = outputs[min_idx]
                map_arr = outputs[max_idx]
            elif len(outputs) == 1:
                # Single output — treat as anomaly_map, score from max
                map_arr = outputs[0]
                score_arr = np.array([float(np.max(outputs[0]))])
            else:
                print(f"  WARN: no outputs for {img_path.name}")
                failed_count += 1
                continue

            # Compute metrics
            # Log output structure for first image of each category
            if processed == 0:
                for oi, odata in enumerate(outputs):
                    print(f"    output[{oi}]: shape={odata.shape} dtype={odata.dtype} "
                          f"size={odata.size}")
                print(f"    → score from output[{min_idx}] (size={score_arr.size}), "
                      f"map from output[{max_idx}] (size={map_arr.size})")

            try:
                metrics = compute_metrics(score_arr, map_arr)
            except Exception as e:
                print(f"  WARN: compute_metrics failed for {img_path.name}: {e}")
                failed_count += 1
                continue

            final_score = metrics[score_mode]

            label = 0 if is_good else 1
            if is_good:
                good_count += 1
            else:
                defect_count += 1

            # Write CSV row
            if csv_writer:
                csv_writer.writerow({
                    "category": category,
                    "image_path": str(img_path),
                    "label": label,
                    "defect_type": sub_name if not is_good else "",
                    "raw_score": f"{metrics['raw_score']:.6f}",
                    "map_max": f"{metrics['map_max']:.6f}",
                    "map_mean": f"{metrics['map_mean']:.6f}",
                    "map_top1": f"{metrics['map_top1']:.6f}",
                    "map_top01": f"{metrics['map_top01']:.6f}",
                    "final_score": f"{final_score:.6f}",
                    "threshold": "",
                })

            processed += 1
            elapsed = time.perf_counter() - t_start
            eta = (elapsed / processed) * (total_images - processed) if processed > 0 else 0
            print(f"\r  [{processed}/{total_images}] {img_path.name:12s}  "
                  f"final={final_score:10.4f}  elapsed={elapsed:.0f}s  ETA={eta:.0f}s",
                  end="", flush=True)

        print()  # newline after progress

    rknn.release()

    elapsed_total = time.perf_counter() - t_start
    print(f"  Done: good={good_count} defect={defect_count} failed={failed_count} "
          f"time={elapsed_total:.1f}s")

    return good_count, defect_count, failed_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate EfficientAD raw scores on MVTec test set using RKNNLite"
    )
    parser.add_argument(
        "--mvtec-root", type=str, required=True,
        help="Root directory of MVTec dataset (contains category/test/ subdirs)",
    )
    parser.add_argument(
        "--model-root", type=str, required=True,
        help="Root directory of EfficientAD RKNN models (contains category/model.rknn)",
    )
    parser.add_argument(
        "--output-csv", type=str, required=True,
        help="Output CSV file path",
    )
    parser.add_argument(
        "--categories", nargs="+", default=None,
        help="Categories to evaluate (default: all 15)",
    )
    parser.add_argument(
        "--score-mode", type=str, default="map_mean",
        choices=SCORE_MODES,
        help="Score mode for final_score (default: map_mean)",
    )
    args = parser.parse_args()

    check_dependencies()

    mvtec_root = Path(args.mvtec_root)
    model_root = Path(args.model_root)
    categories = args.categories if args.categories else CATEGORIES
    score_mode = args.score_mode

    # Validate categories
    cat_set = set(CATEGORIES)
    invalid = [c for c in categories if c not in cat_set]
    if invalid:
        print(f"ERROR: invalid categories: {invalid}")
        print(f"Allowed: {sorted(cat_set)}")
        sys.exit(1)

    # Create output directory
    output_path = Path(args.output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write CSV
    csv_fieldnames = [
        "category", "image_path", "label", "defect_type",
        "raw_score", "map_max", "map_mean", "map_top1", "map_top01",
        "final_score", "threshold",
    ]

    total_good = 0
    total_defect = 0
    total_failed = 0
    category_results = {}

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fieldnames)
        writer.writeheader()

        print(f"EfficientAD RKNN Threshold Calibration")
        print(f"MVTec root: {mvtec_root}")
        print(f"Model root: {model_root}")
        print(f"Score mode: {score_mode}")
        print(f"Output CSV: {output_path}")
        print(f"Categories: {len(categories)}")
        print("=" * 60)

        for cat in categories:
            print(f"\n{'=' * 60}")
            print(f"  [{categories.index(cat)+1}/{len(categories)}] {cat}")
            print(f"{'=' * 60}")

            try:
                g, d, f_cnt = evaluate_category(
                    cat, mvtec_root, model_root, score_mode, writer
                )
                total_good += g
                total_defect += d
                total_failed += f_cnt
                category_results[cat] = (g, d, f_cnt)
            except Exception as e:
                print(f"  [ERROR] {cat}: {e}")
                import traceback
                traceback.print_exc()
                category_results[cat] = (0, 0, 0)

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"  SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Total good images:   {total_good}")
    print(f"  Total defect images: {total_defect}")
    print(f"  Total failed:        {total_failed}")
    print(f"  Total processed:     {total_good + total_defect}")
    print(f"  Categories complete: {sum(1 for g, d, _ in category_results.values() if g > 0 and d > 0)}/{len(categories)}")
    print(f"\n  CSV written to: {output_path}")

    # Per-category summary
    print(f"\n  {'Category':<15s} {'Good':>6s} {'Defect':>6s} {'Failed':>6s}")
    print(f"  {'-' * 40}")
    for cat in categories:
        g, d, f_cnt = category_results.get(cat, (0, 0, 0))
        status = "OK" if g > 0 and d > 0 else "INCOMPLETE"
        print(f"  {cat:<15s} {g:>6d} {d:>6d} {f_cnt:>6d}  {status}")

    # Exit with error if any category has 0 good or 0 defect
    incomplete = [c for c, (g, d, _) in category_results.items() if g == 0 or d == 0]
    if incomplete:
        print(f"\nWARNING: Incomplete categories: {incomplete}")
        sys.exit(1)

    print("\nAll 15 categories complete.")


if __name__ == "__main__":
    main()
