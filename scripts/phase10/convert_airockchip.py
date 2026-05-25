#!/usr/bin/env python3
"""Convert airockchip YOLOv8 ONNX to RKNN FP16.

Input:  models/yolov8n_phase10/yolov8n_metal_nut_cable_best_airockchip.onnx
Output: models/yolov8n_phase10/yolov8n_metal_nut_cable_best_airockchip_fp16.rknn
"""
from __future__ import annotations
import hashlib, sys
from pathlib import Path
from rknn.api import RKNN

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = PROJECT_ROOT / "models" / "yolov8n_phase10"
ONNX_PATH = MODEL_DIR / "yolov8n_metal_nut_cable_best_airockchip.onnx"
RKNN_PATH = MODEL_DIR / "yolov8n_metal_nut_cable_best_airockchip_fp16.rknn"

MEAN_VALUES = [[0, 0, 0]]
STD_VALUES = [[255, 255, 255]]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    print(f"=== airockchip YOLOv8 RKNN FP16 Conversion ===")
    print(f"Input:  {ONNX_PATH}")
    print(f"Output: {RKNN_PATH}")

    rknn = RKNN(verbose=False)

    rknn.config(
        target_platform="rk3588",
        mean_values=MEAN_VALUES,
        std_values=STD_VALUES,
        optimization_level=0,
    )

    ret = rknn.load_onnx(model=str(ONNX_PATH))
    if ret != 0:
        print(f"ERROR: load_onnx failed (ret={ret})")
        sys.exit(1)

    ret = rknn.build(do_quantization=False)
    if ret != 0:
        print(f"ERROR: build failed (ret={ret})")
        sys.exit(1)

    ret = rknn.export_rknn(str(RKNN_PATH))
    if ret != 0:
        print(f"ERROR: export_rknn failed (ret={ret})")
        sys.exit(1)

    rknn.release()

    size = RKNN_PATH.stat().st_size
    digest = sha256(RKNN_PATH)
    print(f"\nExport SUCCESS")
    print(f"  Path:   {RKNN_PATH}")
    print(f"  Size:   {size:,} bytes ({size/1024/1024:.1f} MB)")
    print(f"  SHA256: {digest}")


if __name__ == "__main__":
    main()
