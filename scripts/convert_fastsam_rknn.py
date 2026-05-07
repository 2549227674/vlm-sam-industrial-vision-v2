#!./.venv_rknn/bin/python3
"""Stage 6.3: Convert FastSAM-s ONNX to RKNN INT8 for RK3588.

Requires: rknn-toolkit2 in .venv_rknn (NOT .venv)
Runs on:  PC or cross-compile host (not on RK3588 itself)

Input:  models/fastsam_models/fastsam_s.onnx
Output: models/fastsam_models/fastsam_s.rknn
        models/fastsam_models/accuracy_analysis/

Normalization: YOLOv8 default (0-255 -> 0-1)
    mean=[0, 0, 0], std=[255, 255, 255]

Usage:
    source .venv_rknn/bin/activate
    python scripts/convert_fastsam_rknn.py
    python scripts/convert_fastsam_rknn.py --calib-samples 100
"""

from __future__ import annotations

import argparse
import random
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FASTSAM_DIR = PROJECT_ROOT / "models" / "fastsam_models"
MVTEC_DIR = PROJECT_ROOT / "simulator" / "mvtec"
CATEGORIES = ["metal_nut", "screw", "pill"]
COSINE_THRESHOLD = 0.99

# YOLOv8 normalization: pixel [0,255] -> [0,1]
MEAN_VALUES = [[0, 0, 0]]
STD_VALUES = [[255, 255, 255]]


def create_calib_list(num_samples: int) -> str:
    """Mix good/ images from all 3 categories for INT8 calibration.

    FastSAM is a general segmentation model shared across categories,
    so calibration must cover all three texture distributions.
    """
    random.seed(42)
    per_cat = num_samples // len(CATEGORIES)  # 33
    remainder = num_samples - per_cat * len(CATEGORIES)  # 1

    all_images: list[Path] = []
    for i, cat in enumerate(CATEGORIES):
        good_dir = MVTEC_DIR / cat / "train" / "good"
        if not good_dir.exists():
            raise FileNotFoundError(f"Calibration dir not found: {good_dir}")
        n = per_cat + (1 if i < remainder else 0)
        cat_images = sorted(good_dir.glob("*.png"))[:n]
        if len(cat_images) < n:
            raise ValueError(
                f"{cat}: need {n} images, found {len(cat_images)} in {good_dir}"
            )
        all_images.extend(cat_images)
        print(f"    {cat}: {len(cat_images)} images")

    random.shuffle(all_images)

    calib_file = FASTSAM_DIR / "calib_dataset.txt"
    calib_file.parent.mkdir(parents=True, exist_ok=True)
    with open(calib_file, "w") as f:
        for img in all_images:
            f.write(f"{img.resolve()}\n")

    print(f"  Calibration list: {len(all_images)} mixed images -> {calib_file}")
    return str(calib_file)


def parse_accuracy_report(analysis_dir: Path) -> tuple[float, bool]:
    """Parse error_analysis.txt, return (min_entire_cosine, all_pass).

    Table row format:
      [Conv] /model.0/...   0.99858 | 504.43    0.99858 | 504.43
      entire cos ^                 ^ single cos
    """
    report_path = analysis_dir / "error_analysis.txt"
    if not report_path.exists():
        print(f"  WARNING: report not found at {report_path}")
        return 0.0, False

    # group(1) = entire cosine, group(2) = single cosine
    pattern = re.compile(r"^\[.*?\].*?\s+([\d.]+)\s+\|\s+[\d.]+\s+([\d.]+)")
    min_cosine = 1.0

    with open(report_path) as f:
        for line in f:
            m = pattern.search(line)
            if m:
                val = float(m.group(1))  # entire cosine
                if val < min_cosine:
                    min_cosine = val

    all_pass = min_cosine >= COSINE_THRESHOLD
    return min_cosine, all_pass


def convert_fastsam(calib_samples: int) -> bool:
    """Convert FastSAM-s ONNX to RKNN. Returns True on success."""
    from rknn.api import RKNN

    onnx_path = FASTSAM_DIR / "fastsam_s.onnx"
    rknn_path = FASTSAM_DIR / "fastsam_s.rknn"

    if not onnx_path.exists():
        print(f"  [SKIP] ONNX not found: {onnx_path}")
        return False

    print(f"\n{'=' * 50}")
    print("  Converting: FastSAM-s")
    print(f"{'=' * 50}")

    rknn = RKNN(verbose=False)

    try:
        # 1. Config — YOLOv8 normalization, INT8, rk3588
        print("  [1/5] Config (INT8, rk3588)...")
        ret = rknn.config(
            mean_values=MEAN_VALUES,
            std_values=STD_VALUES,
            target_platform="rk3588",
            quantized_dtype="asymmetric_quantized-8",
        )
        if ret != 0:
            print("  FAIL: config()")
            return False

        # 2. Load ONNX — fixed input size [1,3,640,640]
        print("  [2/5] Load ONNX...")
        ret = rknn.load_onnx(
            model=str(onnx_path),
            inputs=["images"],
            input_size_list=[[1, 3, 640, 640]],
        )
        if ret != 0:
            print("  FAIL: load_onnx()")
            return False

        # 3. Build INT8 quantized model
        print(f"  [3/5] Build INT8 (calib={calib_samples} samples)...")
        calib_file = create_calib_list(calib_samples)
        ret = rknn.build(do_quantization=True, dataset=calib_file)
        if ret != 0:
            print("  FAIL: build()")
            return False

        # 4. Accuracy analysis
        analysis_dir = FASTSAM_DIR / "accuracy_analysis"
        analysis_dir.mkdir(parents=True, exist_ok=True)

        print("  [4/5] Accuracy analysis...")
        with open(calib_file) as f:
            first_image = f.readline().strip()
        rknn.accuracy_analysis(inputs=[first_image], output_dir=str(analysis_dir))

        min_cosine, all_pass = parse_accuracy_report(analysis_dir)
        print(f"  Min cosine similarity: {min_cosine:.4f}")
        if not all_pass:
            print(f"  WARNING: below threshold {COSINE_THRESHOLD}!")

        # 5. Export
        print("  [5/5] Export RKNN...")
        ret = rknn.export_rknn(str(rknn_path))
        if ret != 0:
            print("  FAIL: export_rknn()")
            return False

        print(f"  OK: {rknn_path}")
        return all_pass

    finally:
        rknn.release()


def main() -> None:
    parser = argparse.ArgumentParser(description="FastSAM-s ONNX -> RKNN INT8")
    parser.add_argument("--calib-samples", type=int, default=100,
                        help="Number of good/ images for INT8 calibration")
    args = parser.parse_args()

    try:
        ok = convert_fastsam(args.calib_samples)
    except Exception as e:
        print(f"  ERROR: {e}")
        ok = False

    print(f"\n{'=' * 50}")
    status = "PASS" if ok else "FAIL"
    print(f"  FastSAM-s  {status}  (cosine >= {COSINE_THRESHOLD})")
    print(f"{'=' * 50}")

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
