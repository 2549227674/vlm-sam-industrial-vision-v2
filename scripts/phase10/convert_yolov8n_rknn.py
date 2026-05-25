#!./.venv_rknn/bin/python3
"""Convert YOLOv8n ONNX to RKNN FP16 for RK3588.

Requires: rknn-toolkit2 in .venv_rknn (NOT .venv)
Runs on:  PC or cross-compile host (not on RK3588 itself)

Input:  models/yolov8n_phase10/yolov8n_metal_nut_cable_best.onnx
Output: models/yolov8n_phase10/yolov8n_metal_nut_cable_best_fp16.rknn

Normalization: YOLOv8 default (0-255 -> 0-1)
    mean=[0, 0, 0], std=[255, 255, 255]

Usage:
    source .venv_rknn/bin/activate
    python scripts/phase10/convert_yolov8n_rknn.py
    python scripts/phase10/convert_yolov8n_rknn.py --quantized --calib-samples 50
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = PROJECT_ROOT / "models" / "yolov8n_phase10"
ONNX_PATH = MODEL_DIR / "yolov8n_metal_nut_cable_best.onnx"
RKNN_FP16_PATH = MODEL_DIR / "yolov8n_metal_nut_cable_best_fp16.rknn"
RKNN_INT8_PATH = MODEL_DIR / "yolov8n_metal_nut_cable_best_int8.rknn"

MVTEC_DIR = PROJECT_ROOT / "simulator" / "mvtec"
PHASE10_CLASSES = [
    "metal_nut", "cable",
]

# YOLOv8 normalization: pixel [0,255] -> [0,1]
MEAN_VALUES = [[0, 0, 0]]
STD_VALUES = [[255, 255, 255]]

IMG_SIZE = 640


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def create_calib_list(num_samples: int) -> list[str]:
    """Collect calibration images from phase10 train set."""
    import random
    random.seed(42)

    train_dir = PROJECT_ROOT / "datasets" / "phase10" / "images" / "train"
    if not train_dir.exists():
        print(f"ERROR: train dir not found: {train_dir}")
        sys.exit(1)

    all_images = sorted(train_dir.glob("*.png"))
    if len(all_images) < num_samples:
        print(f"WARNING: only {len(all_images)} images available, using all")
        num_samples = len(all_images)

    selected = random.sample(all_images, num_samples)
    return [str(p) for p in selected]


def convert_fp16() -> None:
    """Convert ONNX to RKNN FP16 (no quantization)."""
    from rknn.api import RKNN

    print(f"=== RKNN FP16 Conversion ===")
    print(f"Input:  {ONNX_PATH}")
    print(f"Output: {RKNN_FP16_PATH}")

    rknn = RKNN(verbose=False)

    # Configure for RK3588
    rknn.config(
        target_platform="rk3588",
        mean_values=MEAN_VALUES,
        std_values=STD_VALUES,
    )

    # Load ONNX
    ret = rknn.load_onnx(model=str(ONNX_PATH))
    if ret != 0:
        print(f"ERROR: load_onnx failed (ret={ret})")
        sys.exit(1)

    # Build FP16 (no quantization)
    ret = rknn.build(do_quantization=False)
    if ret != 0:
        print(f"ERROR: build failed (ret={ret})")
        sys.exit(1)

    # Export
    ret = rknn.export_rknn(str(RKNN_FP16_PATH))
    if ret != 0:
        print(f"ERROR: export_rknn failed (ret={ret})")
        sys.exit(1)

    rknn.release()

    size = RKNN_FP16_PATH.stat().st_size
    digest = sha256(RKNN_FP16_PATH)
    print(f"\nExport SUCCESS")
    print(f"  Path:   {RKNN_FP16_PATH}")
    print(f"  Size:   {size:,} bytes ({size/1024/1024:.1f} MB)")
    print(f"  SHA256: {digest}")


def convert_int8(calib_samples: int) -> None:
    """Convert ONNX to RKNN INT8 with calibration."""
    from rknn.api import RKNN

    print(f"=== RKNN INT8 Conversion ===")
    print(f"Input:  {ONNX_PATH}")
    print(f"Output: {RKNN_INT8_PATH}")
    print(f"Calib:  {calib_samples} samples from phase10 train set")

    calib_list = create_calib_list(calib_samples)
    print(f"  Selected {len(calib_list)} calibration images")

    rknn = RKNN(verbose=False)

    # Configure for RK3588
    rknn.config(
        target_platform="rk3588",
        mean_values=MEAN_VALUES,
        std_values=STD_VALUES,
    )

    # Load ONNX
    ret = rknn.load_onnx(model=str(ONNX_PATH))
    if ret != 0:
        print(f"ERROR: load_onnx failed (ret={ret})")
        sys.exit(1)

    # Build INT8 with calibration
    ret = rknn.build(do_quantization=True, dataset=calib_list)
    if ret != 0:
        print(f"ERROR: build failed (ret={ret})")
        sys.exit(1)

    # Export
    ret = rknn.export_rknn(str(RKNN_INT8_PATH))
    if ret != 0:
        print(f"ERROR: export_rknn failed (ret={ret})")
        sys.exit(1)

    rknn.release()

    size = RKNN_INT8_PATH.stat().st_size
    digest = sha256(RKNN_INT8_PATH)
    print(f"\nExport SUCCESS")
    print(f"  Path:   {RKNN_INT8_PATH}")
    print(f"  Size:   {size:,} bytes ({size/1024/1024:.1f} MB)")
    print(f"  SHA256: {digest}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert YOLOv8n ONNX to RKNN")
    parser.add_argument(
        "--quantized", action="store_true",
        help="Build INT8 with calibration (default: FP16 no-quant)",
    )
    parser.add_argument(
        "--calib-samples", type=int, default=50,
        help="Number of calibration images for INT8 (default: 50)",
    )
    args = parser.parse_args()

    if not ONNX_PATH.exists():
        print(f"ERROR: ONNX not found: {ONNX_PATH}")
        sys.exit(1)

    if args.quantized:
        convert_int8(args.calib_samples)
    else:
        convert_fp16()


if __name__ == "__main__":
    main()
