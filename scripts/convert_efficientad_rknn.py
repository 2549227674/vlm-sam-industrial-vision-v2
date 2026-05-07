#!./.venv_rknn/bin/python3
"""Stage 6.2: Convert EfficientAD-S ONNX to RKNN INT8 for RK3588.

Requires: rknn-toolkit2 in .venv_rknn (NOT .venv)
Runs on:  PC or cross-compile host (not on RK3588 itself)

Input:  models/efficientad_models/{category}/weights/onnx/model.onnx
Output: models/efficientad_models/{category}/model.rknn
        models/efficientad_models/{category}/accuracy_analysis/

Normalization: ImageNet defaults used by Anomalib
    mean=[123.675, 116.28, 103.53], std=[58.395, 57.12, 57.375]

Usage:
    source .venv_rknn/bin/activate
    python scripts/convert_efficientad_rknn.py
    python scripts/convert_efficientad_rknn.py --categories metal_nut
    python scripts/convert_efficientad_rknn.py --calib-samples 100
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models" / "efficientad_models"
MVTEC_DIR = PROJECT_ROOT / "simulator" / "mvtec"
CATEGORIES = ["metal_nut", "screw", "pill"]
MIN_CALIB_SAMPLES = 50
COSINE_THRESHOLD = 0.99

# Anomalib ImageNet normalization (RGB, 0-255 range)
MEAN_VALUES = [[123.675, 116.28, 103.53]]
STD_VALUES = [[58.395, 57.12, 57.375]]


def create_calib_list(category: str, num_samples: int) -> str:
    """Write absolute paths of good/ images to a text file for RKNN calibration."""
    good_dir = MVTEC_DIR / category / "train" / "good"
    if not good_dir.exists():
        raise FileNotFoundError(f"Calibration dir not found: {good_dir}")

    images = sorted(good_dir.glob("*.png"))[:num_samples]
    if len(images) < MIN_CALIB_SAMPLES:
        raise ValueError(
            f"{category}: need >= {MIN_CALIB_SAMPLES} calib images, found {len(images)} in {good_dir}"
        )

    calib_file = MODELS_DIR / category / "calib_dataset.txt"
    calib_file.parent.mkdir(parents=True, exist_ok=True)
    with open(calib_file, "w") as f:
        for img in images:
            f.write(f"{img.resolve()}\n")

    print(f"  Calibration list: {len(images)} images -> {calib_file}")
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


def convert_category(category: str, calib_samples: int) -> bool:
    """Convert one category. Returns True on success."""
    from rknn.api import RKNN

    onnx_path = MODELS_DIR / category / "weights" / "onnx" / "model.onnx"
    rknn_path = MODELS_DIR / category / "model.rknn"

    if not onnx_path.exists():
        print(f"  [SKIP] ONNX not found: {onnx_path}")
        return False

    print(f"\n{'=' * 50}")
    print(f"  Converting: {category}")
    print(f"{'=' * 50}")

    rknn = RKNN(verbose=False)

    try:
        # 1. Config — no rknn_core_num (runtime param, not conversion param)
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

        # 2. Load ONNX

        print("  [2/5] Load ONNX...")
        ret = rknn.load_onnx(
                model=str(onnx_path),
                inputs=['input'],  # 指定输入节点的名称
                input_size_list=[[1, 3, 256, 256]]  # 强制固定动态 batch_size 为 1
        )
        if ret != 0:
            print("  FAIL: load_onnx()")
            return False

        # 3. Build INT8 quantized model
        print(f"  [3/5] Build INT8 (calib={calib_samples} samples)...")
        calib_file = create_calib_list(category, calib_samples)
        ret = rknn.build(do_quantization=True, dataset=calib_file)
        if ret != 0:
            print("  FAIL: build()")
            return False

        # 4. Accuracy analysis
        analysis_dir = MODELS_DIR / category / "accuracy_analysis"
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
    parser = argparse.ArgumentParser(description="EfficientAD-S ONNX -> RKNN INT8")
    parser.add_argument("--categories", nargs="+", default=CATEGORIES)
    parser.add_argument("--calib-samples", type=int, default=100,
                        help="Number of good/ images for INT8 calibration")
    args = parser.parse_args()

    results: dict[str, bool] = {}

    for cat in args.categories:
        try:
            results[cat] = convert_category(cat, args.calib_samples)
        except Exception as e:
            print(f"  ERROR ({cat}): {e}")
            results[cat] = False

    # Summary
    print(f"\n{'=' * 50}")
    print("  Summary")
    print(f"{'=' * 50}")
    ok_count = 0
    for cat, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  {cat:12s}  {status}")
        if ok:
            ok_count += 1

    total = len(results)
    print(f"\n  {ok_count}/{total} categories passed (cosine >= {COSINE_THRESHOLD})")

    if ok_count < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
