#!/usr/bin/env python3
"""Evaluate EfficientAD raw scores on MVTec test set for T2 threshold tuning.

Runs model_raw.onnx (pre-postprocessor) on all test images and computes
five candidate metrics:

  raw_score   — ReduceMax of anomaly map (= map_max by definition)
  map_max     — max pixel in raw anomaly map
  map_mean    — mean of entire raw anomaly map
  map_top1    — mean of top-1% pixels
  map_top01   — mean of top-0.1% pixels

For each metric: per-class stats (good/defect), threshold sweep, AUROC,
and a recommended T2 high-recall coarse-filter threshold.

Priority: high recall (catch defects), NOT zero false positives.

Usage:
    source .venv/bin/activate
    python scripts/evaluate_efficientad_raw_scores.py --categories bottle
    python scripts/evaluate_efficientad_raw_scores.py --categories bottle cable pill
    python scripts/evaluate_efficientad_raw_scores.py --categories bottle --csv scores.csv
    python scripts/evaluate_efficientad_raw_scores.py --recall-target 0.95 --categories bottle
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models" / "efficientad_models"
MVTEC_DIR = PROJECT_ROOT / "simulator" / "mvtec"

# MVTec AD full 15 classes
CATEGORIES = [
    "bottle", "cable", "capsule", "carpet", "grid",
    "hazelnut", "leather", "metal_nut", "pill", "screw",
    "tile", "toothbrush", "transistor", "wood", "zipper",
]
CATEGORY_SET = frozenset(CATEGORIES)

INPUT_SIZE = 256
MEAN = np.array([123.675, 116.28, 103.53], dtype=np.float32)
STD = np.array([58.395, 57.12, 57.375], dtype=np.float32)

# Threshold sweep grid: try many candidate cutoffs
SWEEP_STEPS = 200


def _preprocess(img_path: Path) -> np.ndarray:
    """Load and normalize a single image to NCHW float32."""
    img = Image.open(img_path).convert("RGB").resize((INPUT_SIZE, INPUT_SIZE))
    arr = np.array(img, dtype=np.float32)
    arr = (arr - MEAN) / STD
    return arr.transpose(2, 0, 1)[np.newaxis]  # [1, 3, 256, 256]


def _compute_metrics(raw_score: np.ndarray, raw_map: np.ndarray) -> dict[str, float]:
    """Extract five metrics from a single inference result."""
    score_val = float(raw_score[0, 0])
    flat = raw_map.flatten()
    n_pixels = len(flat)

    top1_n = max(1, n_pixels // 100)
    top01_n = max(1, n_pixels // 1000)

    sorted_desc = np.sort(flat)[::-1]

    return {
        "raw_score": score_val,
        "map_max": float(flat.max()),
        "map_mean": float(flat.mean()),
        "map_top1": float(sorted_desc[:top1_n].mean()),
        "map_top01": float(sorted_desc[:top01_n].mean()),
    }


def _percentiles(values: np.ndarray) -> dict[str, float]:
    """Compute min, p50, p90, p95, p99, max."""
    return {
        "min": float(np.min(values)),
        "p50": float(np.percentile(values, 50)),
        "p90": float(np.percentile(values, 90)),
        "p95": float(np.percentile(values, 95)),
        "p99": float(np.percentile(values, 99)),
        "max": float(np.max(values)),
    }


def _threshold_sweep(
    good_vals: np.ndarray, defect_vals: np.ndarray, recall_target: float
) -> list[dict]:
    """Sweep thresholds and find the best one per metric for high recall.

    Returns one dict per metric with recommended threshold, recall, fpr.
    """
    metric_names = ["raw_score", "map_max", "map_mean", "map_top1", "map_top01"]
    recommendations = []

    for metric in metric_names:
        gv = good_vals[metric]
        dv = defect_vals[metric]

        if len(gv) == 0 or len(dv) == 0:
            recommendations.append({
                "metric": metric,
                "threshold": float("nan"),
                "recall": 0.0,
                "fpr": float("nan"),
                "note": "insufficient data",
            })
            continue

        all_vals = np.concatenate([gv, dv])
        lo, hi = float(all_vals.min()), float(all_vals.max())
        if lo == hi:
            recommendations.append({
                "metric": metric,
                "threshold": lo,
                "recall": 1.0,
                "fpr": 1.0 if len(gv) > 0 else 0.0,
                "note": "degenerate (all equal)",
            })
            continue

        thresholds = np.linspace(lo, hi, SWEEP_STEPS)

        best = None
        # Search from highest threshold downward: first one meeting recall
        # has the lowest FPR (fewest good images above threshold).
        for thr in reversed(thresholds):
            recall = float(np.mean(dv >= thr))
            if recall >= recall_target:
                fpr = float(np.mean(gv >= thr))
                best = {
                    "metric": metric,
                    "threshold": float(thr),
                    "recall": recall,
                    "fpr": fpr,
                }
                break

        if best is None:
            # Cannot reach recall target — pick the threshold with max recall
            max_recall_thr = lo
            max_recall = 0.0
            for thr in thresholds:
                recall = float(np.mean(dv >= thr))
                if recall > max_recall:
                    max_recall = recall
                    max_recall_thr = float(thr)
            best = {
                "metric": metric,
                "threshold": max_recall_thr,
                "recall": max_recall,
                "fpr": float(np.mean(gv >= max_recall_thr)),
                "note": f"recall target {recall_target} unreachable",
            }

        recommendations.append(best)

    return recommendations


def _compute_auroc(good_vals: np.ndarray, defect_vals: np.ndarray) -> dict[str, float | None]:
    """Compute AUROC for each metric. Returns None if sklearn fails."""
    try:
        from sklearn.metrics import roc_auc_score
    except ImportError:
        return {m: None for m in ["raw_score", "map_max", "map_mean", "map_top1", "map_top01"]}

    aurocs = {}
    for metric in ["raw_score", "map_max", "map_mean", "map_top1", "map_top01"]:
        gv = good_vals[metric]
        dv = defect_vals[metric]
        if len(gv) == 0 or len(dv) == 0:
            aurocs[metric] = None
            continue
        y_true = np.concatenate([np.zeros(len(gv)), np.ones(len(dv))])
        y_score = np.concatenate([gv, dv])
        try:
            aurocs[metric] = float(roc_auc_score(y_true, y_score))
        except ValueError:
            aurocs[metric] = None
    return aurocs


def evaluate_category(
    category: str,
    recall_target: float,
    csv_writer: csv.DictWriter | None = None,
) -> bool:
    """Evaluate one category. Returns True on success."""
    model_path = MODELS_DIR / category / "weights" / "onnx" / "model_raw.onnx"
    test_dir = MVTEC_DIR / category / "test"

    if not model_path.exists():
        print(f"  [SKIP] model_raw.onnx not found: {model_path}")
        return False
    if not test_dir.exists():
        print(f"  [SKIP] test dir not found: {test_dir}")
        return False

    so = ort.SessionOptions()
    so.intra_op_num_threads = os.cpu_count() or 4
    so.inter_op_num_threads = 1
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    sess = ort.InferenceSession(str(model_path), sess_options=so)

    metric_names = ["raw_score", "map_max", "map_mean", "map_top1", "map_top01"]
    good_vals: dict[str, list[float]] = {m: [] for m in metric_names}
    defect_vals: dict[str, list[float]] = {m: [] for m in metric_names}

    print(f"\n{'=' * 60}")
    print(f"  {category}")
    print(f"{'=' * 60}")

    # Count total images for progress tracking
    total_images = 0
    for sub_dir in test_dir.iterdir():
        if sub_dir.is_dir():
            total_images += sum(
                1 for p in sub_dir.iterdir()
                if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp")
            )
    processed = 0
    t_start = time.perf_counter()

    # Iterate test subdirs
    for sub_dir in sorted(test_dir.iterdir()):
        if not sub_dir.is_dir():
            continue
        sub_name = sub_dir.name
        is_good = sub_name == "good"

        images = sorted(
            p for p in sub_dir.iterdir()
            if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp")
        )
        if not images:
            continue

        for img_path in images:
            inp = _preprocess(img_path)
            raw_score, raw_map = sess.run(None, {"input": inp})
            metrics = _compute_metrics(raw_score, raw_map)

            bucket = good_vals if is_good else defect_vals
            for m in metric_names:
                bucket[m].append(metrics[m])

            if csv_writer:
                csv_writer.writerow({
                    "category": category,
                    "label": "good" if is_good else "defect",
                    "defect_type": sub_name if not is_good else "",
                    "image": img_path.name,
                    **{m: f"{metrics[m]:.4f}" for m in metric_names},
                })

            processed += 1
            elapsed = time.perf_counter() - t_start
            eta = (elapsed / processed) * (total_images - processed)
            print(f"\r  [{processed}/{total_images}] {img_path.name:12s}  "
                  f"elapsed={elapsed:.0f}s  ETA={eta:.0f}s  ", end="", flush=True)

        # Per-subgroup summary line
        print()  # clear progress line
        n = len(images)
        tag = "good" if is_good else sub_name
        # Quick stats for this sub-group
        rs = defect_vals["raw_score"] if not is_good else good_vals["raw_score"]
        if is_good:
            rs_last = good_vals["raw_score"][-n:]
        else:
            rs_last = defect_vals["raw_score"][-n:]
        print(f"  {tag:20s}  n={n:4d}  raw_score mean={np.mean(rs_last):8.2f}  "
              f"max={np.max(rs_last):8.2f}")

    good_arrays = {m: np.array(v) for m, v in good_vals.items()}
    defect_arrays = {m: np.array(v) for m, v in defect_vals.items()}

    # Per-metric statistics
    print(f"\n  {'Metric':<12s}  {'':>8s}  {'min':>8s}  {'p50':>8s}  {'p90':>8s}  "
          f"{'p95':>8s}  {'p99':>8s}  {'max':>8s}")
    print(f"  {'-' * 80}")

    for metric in metric_names:
        for label, arrays in [("GOOD ", good_arrays), ("DEFECT", defect_arrays)]:
            vals = arrays[metric]
            if len(vals) == 0:
                continue
            pct = _percentiles(vals)
            print(f"  {metric:<12s}  {label:>8s}  {pct['min']:8.2f}  {pct['p50']:8.2f}  "
                  f"{pct['p90']:8.2f}  {pct['p95']:8.2f}  {pct['p99']:8.2f}  {pct['max']:8.2f}")

    # AUROC
    aurocs = _compute_auroc(good_arrays, defect_arrays)
    print(f"\n  AUROC:")
    for metric in metric_names:
        val = aurocs[metric]
        if val is not None:
            print(f"    {metric:<12s}  {val:.4f}")
        else:
            print(f"    {metric:<12s}  N/A")

    # Threshold sweep for high recall
    recs = _threshold_sweep(good_arrays, defect_arrays, recall_target)
    print(f"\n  T2 High-Recall Recommendations (target recall >= {recall_target}):")
    print(f"  {'Metric':<12s}  {'Threshold':>10s}  {'Recall':>8s}  {'FPR':>8s}  Note")
    print(f"  {'-' * 60}")
    for r in recs:
        note = r.get("note", "")
        print(f"  {r['metric']:<12s}  {r['threshold']:10.2f}  {r['recall']:8.4f}  "
              f"{r['fpr']:8.4f}  {note}")

    # Pick the best metric: among those reaching recall target, pick lowest FPR
    viable = [r for r in recs if r["recall"] >= recall_target and not r.get("note")]
    if viable:
        best = min(viable, key=lambda x: x["fpr"])
    elif recs:
        best = max(recs, key=lambda x: x["recall"])
    else:
        best = {"metric": "N/A", "threshold": 0, "recall": 0, "fpr": 0}

    print(f"\n  >>> Recommended T2 config for '{category}':")
    print(f"      metric={best['metric']}  threshold={best['threshold']:.4f}  "
          f"recall={best['recall']:.4f}  fpr={best['fpr']:.4f}")

    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate EfficientAD raw scores for T2 threshold tuning"
    )
    parser.add_argument(
        "--categories", nargs="+", required=True,
        help="Category(ies) to evaluate (one at a time recommended)",
    )
    parser.add_argument(
        "--recall-target", type=float, default=0.95,
        help="Minimum recall for T2 recommendation (default: 0.95)",
    )
    parser.add_argument(
        "--csv", type=str, default=None,
        help="Optional: write per-image scores to CSV file",
    )
    args = parser.parse_args()

    invalid = [c for c in args.categories if c not in CATEGORY_SET]
    if invalid:
        print(f"ERROR: invalid categories: {invalid}")
        print(f"Allowed: {sorted(CATEGORY_SET)}")
        sys.exit(1)

    csv_file = None
    csv_writer = None
    if args.csv:
        csv_file = open(args.csv, "w", newline="")
        fieldnames = ["category", "label", "defect_type", "image",
                       "raw_score", "map_max", "map_mean", "map_top1", "map_top01"]
        csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        csv_writer.writeheader()

    results: dict[str, bool] = {}
    for cat in args.categories:
        try:
            results[cat] = evaluate_category(cat, args.recall_target, csv_writer)
        except Exception as e:
            print(f"  [ERROR] {cat}: {e}")
            import traceback
            traceback.print_exc()
            results[cat] = False

    if csv_file:
        csv_file.close()
        print(f"\nCSV written to: {args.csv}")

    # Summary
    ok = sum(1 for v in results.values() if v)
    fail = sum(1 for v in results.values() if not v)
    print(f"\nSummary: PASS={ok}  FAIL={fail}  total={len(results)}")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
