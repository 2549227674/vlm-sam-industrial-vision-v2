#!/usr/bin/env python3
"""Export EfficientAD-S ONNX with raw (pre-postprocessor) outputs only.

Strips the Clip-based post_processor (pred_score / anomaly_map are clipped
to [0,1] and useless for threshold tuning) and exposes the two tensors
before that stage:

  /model/ReduceMax_output_0  ->  raw_score       shape [1, 1]
  /model/Add_output_0        ->  raw_anomaly_map  shape [1, 1, 256, 256]

These raw values are needed by evaluate_efficientad_raw_scores.py to find
the right T2 coarse-filter threshold on the RK3588 pipeline.

Input:  models/efficientad_models/{category}/weights/onnx/model.onnx
Output: models/efficientad_models/{category}/weights/onnx/model_raw.onnx

Usage:
    source .venv/bin/activate
    python scripts/export_efficientad_raw_onnx.py                        # all 15 classes
    python scripts/export_efficientad_raw_onnx.py --categories bottle    # single class
    python scripts/export_efficientad_raw_onnx.py --categories bottle cable pill
    python scripts/export_efficientad_raw_onnx.py --force               # overwrite existing
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import onnx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models" / "efficientad_models"

# MVTec AD full 15 classes
CATEGORIES = [
    "bottle", "cable", "capsule", "carpet", "grid",
    "hazelnut", "leather", "metal_nut", "pill", "screw",
    "tile", "toothbrush", "transistor", "wood", "zipper",
]
CATEGORY_SET = frozenset(CATEGORIES)

# Tensor names in the Anomalib EfficientAD-S ONNX graph
RAW_SCORE_TENSOR = "/model/ReduceMax_output_0"
RAW_MAP_TENSOR = "/model/Add_output_0"
RAW_SCORE_NAME = "raw_score"
RAW_MAP_NAME = "raw_anomaly_map"


def _find_tensor_names(model: onnx.ModelProto) -> tuple[str | None, str | None]:
    """Return the actual tensor names that match our targets.

    The ONNX graph produced by Anomalib uses deterministic node output names,
    but we search by suffix to be resilient to minor naming variations.
    """
    all_outputs: set[str] = set()
    for node in model.graph.node:
        for out in (node.output or []):
            all_outputs.add(out)

    score_name = None
    map_name = None
    for name in all_outputs:
        if name.endswith("ReduceMax_output_0"):
            score_name = name
        if name.endswith("Add_output_0"):
            map_name = name

    return score_name, map_name


def export_raw(category: str, force: bool) -> bool:
    """Strip post-processor and export raw ONNX. Returns True on success."""
    onnx_dir = MODELS_DIR / category / "weights" / "onnx"
    src_path = onnx_dir / "model.onnx"
    dst_path = onnx_dir / "model_raw.onnx"

    if not src_path.exists():
        print(f"  [SKIP] ONNX not found: {src_path}")
        return False

    if dst_path.exists() and not force:
        print(f"  [SKIP] already exists: {dst_path}  (use --force to overwrite)")
        return True

    m = onnx.load(str(src_path))

    # Locate tensors
    score_name, map_name = _find_tensor_names(m)
    if score_name is None:
        print(f"  [ERROR] {category}: ReduceMax_output_0 tensor not found, skipping")
        return False
    if map_name is None:
        print(f"  [ERROR] {category}: Add_output_0 tensor not found, skipping")
        return False

    # Remove ALL graph outputs
    del m.graph.output[:]

    # Append Identity nodes to expose raw tensors as graph outputs
    score_identity = onnx.helper.make_node(
        "Identity",
        inputs=[score_name],
        outputs=[RAW_SCORE_NAME],
    )
    map_identity = onnx.helper.make_node(
        "Identity",
        inputs=[map_name],
        outputs=[RAW_MAP_NAME],
    )
    m.graph.node.append(score_identity)
    m.graph.node.append(map_identity)

    # Register new graph outputs with explicit shapes
    score_out = onnx.helper.make_tensor_value_info(
        RAW_SCORE_NAME, onnx.TensorProto.FLOAT, [1, 1]
    )
    map_out = onnx.helper.make_tensor_value_info(
        RAW_MAP_NAME, onnx.TensorProto.FLOAT, [1, 1, 256, 256]
    )
    m.graph.output.append(score_out)
    m.graph.output.append(map_out)

    # Validate
    onnx.checker.check_model(m)

    # Save
    onnx.save(m, str(dst_path))
    print(f"  [OK] {dst_path}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export EfficientAD raw ONNX (pre-postprocessor outputs)"
    )
    parser.add_argument(
        "--categories", nargs="+", default=CATEGORIES,
        help="Categories to export (default: all 15)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing model_raw.onnx",
    )
    args = parser.parse_args()

    invalid = [c for c in args.categories if c not in CATEGORY_SET]
    if invalid:
        print(f"ERROR: invalid categories: {invalid}")
        print(f"Allowed: {sorted(CATEGORY_SET)}")
        sys.exit(1)

    results: dict[str, bool] = {}
    for cat in args.categories:
        try:
            results[cat] = export_raw(cat, args.force)
        except Exception as e:
            print(f"  [ERROR] {cat}: {e}")
            results[cat] = False

    # Summary
    ok = sum(1 for v in results.values() if v)
    fail = sum(1 for v in results.values() if not v)
    print(f"\nSummary: PASS={ok}  FAIL={fail}  total={len(results)}")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
