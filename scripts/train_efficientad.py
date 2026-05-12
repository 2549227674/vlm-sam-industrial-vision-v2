#!/usr/bin/env python3
"""Train EfficientAD-S on MVTec AD categories and export to ONNX.

Usage:
    python scripts/train_efficientad.py                        # all 3 categories
    python scripts/train_efficientad.py --categories metal_nut # single category
    python scripts/train_efficientad.py --epochs 20            # custom epochs (default)
    python scripts/train_efficientad.py --verify-only          # just check ONNX files
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Project root: two levels up from this script
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# v1 初版 3 类：["metal_nut", "screw", "pill"]
# v2 重做 15 类（执行前先 ls simulator/mvtec/ 确认实际目录名）
CATEGORIES = [
    "bottle", "cable", "capsule", "carpet", "grid", "hazelnut", "leather",
    "metal_nut", "pill", "screw", "tile", "toothbrush", "transistor",
    "wood", "zipper",
]
MVTEC_ROOT = PROJECT_ROOT / "simulator" / "mvtec"
IMAGENET_DIR = PROJECT_ROOT / "datasets" / "imagenette"
EXPORT_BASE = PROJECT_ROOT / "models" / "efficientad_models"
RESULTS_DIR = PROJECT_ROOT / "results" / "efficientad"

# v1 初版实测值（3 类）；15 类参考值来自 Anomalib benchmark
REFERENCE_AUROC = {
    "bottle": 0.983,
    "cable": 0.973,
    "capsule": 0.988,
    "carpet": 0.990,
    "grid": 0.985,
    "hazelnut": 0.977,
    "leather": 0.990,
    "metal_nut": 0.979,
    "pill": 0.987,
    "screw": 0.960,
    "tile": 0.984,
    "toothbrush": 0.983,
    "transistor": 0.978,
    "wood": 0.975,
    "zipper": 0.982,
}


def train_category(category: str, max_epochs: int) -> dict:
    """Train EfficientAD-S on one MVTec category, test, and export ONNX."""
    from anomalib.data import MVTecAD
    from anomalib.deploy import ExportType
    from anomalib.engine import Engine
    from anomalib.models import EfficientAd

    print(f"\n{'=' * 60}")
    print(f"  Training EfficientAD-S: {category}")
    print(f"{'=' * 60}\n")

    # Dataset -- EfficientAD requires train_batch_size=1
    datamodule = MVTecAD(
        root=str(MVTEC_ROOT),
        category=category,
        train_batch_size=1,
        eval_batch_size=32,
        num_workers=4,
    )

    # Model -- default model_size="small", pre-processor resizes to 256x256.
    # imagenet_dir: Teacher network needs Imagenette (~1.4GB, 10-class ImageNet
    # subset) for distillation pre-training before fit(). Auto-downloads if absent.
    model = EfficientAd(model_size="small", imagenet_dir=str(IMAGENET_DIR))

    # Train
    engine = Engine(
        max_epochs=max_epochs,
        default_root_dir=str(RESULTS_DIR / category),
    )

    t0 = time.perf_counter()
    engine.fit(model=model, datamodule=datamodule)
    train_sec = time.perf_counter() - t0

    # Test -- returns list[dict] with image_AUROC, pixel_AUROC, etc.
    test_results = engine.test(model=model, datamodule=datamodule)

    # Export ONNX -- Anomalib's _create_export_root appends weights/onnx/
    export_root = EXPORT_BASE / category
    export_root.mkdir(parents=True, exist_ok=True)

    engine.export(
        model=model,
        export_type=ExportType.ONNX,
        export_root=str(export_root),
        input_size=(256, 256),
    )

    onnx_path = export_root / "weights" / "onnx" / "model.onnx"
    result = {
        "category": category,
        "train_sec": train_sec,
        "test_results": test_results,
        "onnx_path": str(onnx_path),
        "onnx_exists": onnx_path.exists(),
    }

    # Report AUROC -- key name varies across Anomalib versions
    if test_results:
        img_auroc = (
            test_results[0].get("image_AUROC")
            or test_results[0].get("image_auroc")
            or test_results[0].get("Image AUROC")
        )
        if img_auroc is not None:
            ref = REFERENCE_AUROC.get(category, 0)
            result["image_auroc"] = img_auroc
            print(f"\n  image_AUROC = {img_auroc:.4f}  (reference: {ref:.3f})")

    print(f"  Training time: {train_sec:.1f}s")
    print(f"  ONNX exported: {onnx_path}")

    return result


def verify_onnx(categories: list[str]) -> bool:
    """Verify ONNX files: exist, loadable, and contain all 3 sub-networks.

    EfficientAD-S has Teacher + Student + Autoencoder three sub-networks.
    Anomalib merges them into a single ONNX exporting 4 tensors:
    pred_score, pred_label, anomaly_map, pred_mask. We check:
      1. File exists and loads via onnxruntime
      2. Spatial input shape is (3, 256, 256) -- batch dim is dynamic
      3. At least 2 output tensors (pred_score + anomaly_map at minimum)
      4. ONNX graph node count > 200 (a single sub-network ~50-80 nodes,
         three merged should be well above 200)
    """
    try:
        import onnxruntime as ort
    except ImportError:
        print("WARNING: onnxruntime not installed, skipping load verification")
        print("  Install with: pip install onnxruntime")
        ort = None

    all_ok = True
    for cat in categories:
        onnx_path = EXPORT_BASE / cat / "weights" / "onnx" / "model.onnx"
        if not onnx_path.exists():
            print(f"  MISSING: {onnx_path}")
            all_ok = False
            continue

        size_mb = onnx_path.stat().st_size / (1024 * 1024)
        print(f"  {cat}/model.onnx  ({size_mb:.1f} MB)")

        # --- Check 1-3: onnxruntime session ---
        if ort is not None:
            try:
                sess = ort.InferenceSession(str(onnx_path))
                inputs = sess.get_inputs()
                outputs = sess.get_outputs()

                # Input shape check -- ONNX exports dynamic batch by default
                in_shape = inputs[0].shape
                # batch dim may be 'batch_size' (str) or 1; verify C,H,W
                spatial = in_shape[1:]  # skip batch dim
                if list(spatial) != [3, 256, 256]:
                    print(f"    WARN: spatial shape {list(spatial)}, expected [3, 256, 256]")

                # Output check: EfficientAD ONNX exports 4 tensors:
                # pred_score, pred_label, anomaly_map, pred_mask.
                # Only pred_score + anomaly_map are needed downstream (RKNN);
                # the other two are post-processor additions. Require >= 2.
                n_outputs = len(outputs)
                if n_outputs < 2:
                    print(f"    FAIL: only {n_outputs} output(s), expected >=2 "
                          f"(anomaly_map + pred_score). Sub-networks may be incomplete.")
                    all_ok = False
                else:
                    out_desc = ", ".join(
                        f"{o.name}{list(o.shape)}" for o in outputs
                    )
                    print(f"    inputs:  {inputs[0].name}{list(in_shape)}  (batch=dynamic)")
                    print(f"    outputs: {out_desc}  ({n_outputs} tensors)")

            except Exception as e:
                print(f"    FAIL to load: {e}")
                all_ok = False

        # --- Check 4: ONNX graph node count (sub-network completeness) ---
        try:
            import onnx
            model = onnx.load(str(onnx_path))
            n_nodes = len(model.graph.node)
            if n_nodes < 200:
                print(f"    FAIL: only {n_nodes} nodes in graph (expected >200 "
                      f"for Teacher+Student+AE merged). Sub-networks may be missing.")
                all_ok = False
            else:
                print(f"    graph: {n_nodes} nodes  OK")
        except ImportError:
            print("    (onnx package not installed, skipping graph node check)")
        except Exception as e:
            print(f"    WARN: onnx graph check failed: {e}")

    return all_ok


def main() -> None:
    import pytorch_lightning as pl
    pl.seed_everything(42, workers=True)
    parser = argparse.ArgumentParser(description="Train EfficientAD-S on MVTec AD")
    parser.add_argument(
        "--categories",
        nargs="+",
        default=CATEGORIES,
        choices=CATEGORIES,
        help="Categories to train (default: all 15)",
    )
    parser.add_argument("--epochs", type=int, default=20, help="Max epochs (default: 20)")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing ONNX files, skip training",
    )
    args = parser.parse_args()

    if args.verify_only:
        print("Verifying ONNX files...\n")
        ok = verify_onnx(args.categories)
        sys.exit(0 if ok else 1)

    print(f"EfficientAD-S training: {len(args.categories)} category(ies), {args.epochs} epochs")
    print(f"MVTec dataset: {MVTEC_ROOT}")
    print(f"Export base:   {EXPORT_BASE}")

    results = []
    for cat in args.categories:
        result = train_category(cat, args.epochs)
        results.append(result)

    # Summary
    print(f"\n{'=' * 60}")
    print("  Summary")
    print(f"{'=' * 60}")
    for r in results:
        auroc = r.get("image_auroc", "N/A")
        ref = REFERENCE_AUROC.get(r["category"], 0)
        status = "OK" if r["onnx_exists"] else "MISSING"
        auroc_str = f"{auroc:.4f}" if isinstance(auroc, float) else auroc
        print(f"  {r['category']:12s}  AUROC={auroc_str}  ref={ref:.3f}  ONNX={status}  ({r['train_sec']:.0f}s)")

    # Verify
    print()
    ok = verify_onnx(args.categories)
    if ok:
        print("\nAll ONNX files verified successfully.")
    else:
        print("\nSome ONNX files are missing or broken!")
        sys.exit(1)


if __name__ == "__main__":
    main()
