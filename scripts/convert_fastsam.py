#!/usr/bin/env python3
"""Export FastSAM-s.pt to ONNX and verify with onnxruntime.

Input:  models/fastsam_models/FastSAM-s.pt
Output: models/fastsam_models/fastsam_s.onnx  (640×640, static shape, opset 12)

Usage:
    python scripts/convert_fastsam.py
    python scripts/convert_fastsam.py --weights path/to/FastSAM-s.pt
    python scripts/convert_fastsam.py --imgsz 640 --opset 12
"""

import argparse
import shutil
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WEIGHTS = PROJECT_ROOT / "models" / "fastsam_models" / "FastSAM-s.pt"
FINAL_NAME = "fastsam_s.onnx"

# FastSAM-s 640×640 expected output shapes
EXPECTED_DET_SHAPE = (1, 37, 8400)    # 4(bbox) + 1(class) + 32(mask coef), 8400 anchors
EXPECTED_PROTO_SHAPE = (1, 32, 160, 160)  # 32 prototypes at 1/4 input res


def check_onnxsim() -> bool:
    try:
        import onnxsim  # noqa: F401
        return True
    except ImportError:
        return False


def export_onnx(weights: Path, imgsz: int, opset: int) -> Path:
    from ultralytics import YOLO

    print(f"Loading model: {weights}")
    model = YOLO(str(weights))

    can_simplify = check_onnxsim()
    if not can_simplify:
        print("WARNING: onnxsim not installed, simplify=False. Install with: pip install onnxsim")

    print(f"Exporting ONNX (imgsz={imgsz}, opset={opset}, simplify={can_simplify})...")
    exported = model.export(format="onnx", imgsz=imgsz, opset=opset,
                            simplify=can_simplify, dynamic=False)

    # Ultralytics names output after .pt stem (FastSAM-s.onnx); rename to fastsam_s.onnx
    exported_path = Path(exported)
    final_path = exported_path.parent / FINAL_NAME
    if exported_path != final_path:
        shutil.move(str(exported_path), str(final_path))
        print(f"Renamed: {exported_path.name} -> {FINAL_NAME}")

    return final_path


def verify_onnx(onnx_path: Path, imgsz: int) -> None:
    import numpy as np
    import onnxruntime as ort

    print(f"\nVerifying: {onnx_path}")
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

    print("Inputs:")
    for inp in sess.get_inputs():
        print(f"  {inp.name}: {inp.shape} ({inp.type})")
    print("Outputs:")
    for out in sess.get_outputs():
        print(f"  {out.name}: {out.shape} ({out.type})")

    dummy = np.random.randn(1, 3, imgsz, imgsz).astype(np.float32)
    input_name = sess.get_inputs()[0].name

    t0 = time.perf_counter()
    results = sess.run(None, {input_name: dummy})
    elapsed_ms = (time.perf_counter() - t0) * 1000

    print(f"\nInference: {elapsed_ms:.1f} ms")
    for i, r in enumerate(results):
        print(f"  output[{i}]: {r.shape}")

    # Hard shape assertions
    assert len(results) == 2, f"Expected 2 outputs, got {len(results)}"
    assert results[0].shape == EXPECTED_DET_SHAPE, \
        f"Detection output mismatch: {results[0].shape} != {EXPECTED_DET_SHAPE}"
    assert results[1].shape == EXPECTED_PROTO_SHAPE, \
        f"Proto output mismatch: {results[1].shape} != {EXPECTED_PROTO_SHAPE}"

    print("Shape check PASSED.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export FastSAM-s to ONNX")
    parser.add_argument("--weights", type=str, default=str(DEFAULT_WEIGHTS))
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--opset", type=int, default=12,
                        help="RKNN Toolkit2 prefers opset 12")
    parser.add_argument("--verify-only", action="store_true",
                        help="Skip export, only verify existing ONNX")
    args = parser.parse_args()

    weights = Path(args.weights).resolve()
    onnx_path = weights.parent / FINAL_NAME

    if args.verify_only:
        if not onnx_path.exists():
            raise FileNotFoundError(f"ONNX not found: {onnx_path}")
        verify_onnx(onnx_path, args.imgsz)
        return

    if not weights.exists():
        raise FileNotFoundError(f"Weight file not found: {weights}")

    onnx_path = export_onnx(weights, args.imgsz, args.opset)
    verify_onnx(onnx_path, args.imgsz)
    print(f"\nDone. ONNX ready at: {onnx_path}")


if __name__ == "__main__":
    main()
