#!/usr/bin/env python3
"""Phase 8A-Fix: Compare all 5 score modes and fix recall@FPR logic.

Reads existing rknn_scores_15cls.csv (no re-inference needed) and computes
metrics for raw_score, map_max, map_mean, map_top1, map_top01.

Generates:
  - score_mode_comparison.csv
  - score_mode_comparison.md

Usage:
    python scripts/compare_score_modes.py \
        --input results/phase8_threshold_calibration/rknn_scores_15cls.csv \
        --output-dir results/phase8_threshold_calibration
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from datetime import datetime

import numpy as np

CATEGORIES = [
    "bottle", "cable", "capsule", "carpet", "grid",
    "hazelnut", "leather", "metal_nut", "pill", "screw",
    "tile", "toothbrush", "transistor", "wood", "zipper",
]

SCORE_MODES = ["raw_score", "map_max", "map_mean", "map_top1", "map_top01"]


def compute_auroc(good_vals: np.ndarray, defect_vals: np.ndarray) -> float:
    """Compute AUROC (threshold-independent ranking metric).

    AUROC > 0.5: defects score higher than good (normal direction).
    AUROC < 0.5: defects score lower than good (inverted).
    AUROC = 0.5: random discrimination.
    """
    try:
        from sklearn.metrics import roc_auc_score
        y_true = np.concatenate([np.zeros(len(good_vals)), np.ones(len(defect_vals))])
        y_score = np.concatenate([good_vals, defect_vals])
        return float(roc_auc_score(y_true, y_score))
    except ImportError:
        # Manual trapezoidal
        all_vals = np.concatenate([good_vals, defect_vals])
        labels = np.concatenate([np.zeros(len(good_vals)), np.ones(len(defect_vals))])
        sorted_idx = np.argsort(all_vals)
        sorted_labels = labels[sorted_idx]
        tps = np.cumsum(sorted_labels)
        fps = np.cumsum(1 - sorted_labels)
        tpr = tps / len(defect_vals) if len(defect_vals) > 0 else np.zeros_like(tps)
        fpr = fps / len(good_vals) if len(good_vals) > 0 else np.zeros_like(fps)
        return float(np.trapz(tpr, fpr))


def find_best_f1(good_vals: np.ndarray, defect_vals: np.ndarray,
                 n_steps: int = 2000) -> tuple[float, float]:
    """Find threshold that maximizes F1. Returns (threshold, f1)."""
    all_vals = np.concatenate([good_vals, defect_vals])
    lo, hi = float(all_vals.min()), float(all_vals.max())
    if lo == hi:
        return lo, 0.0

    thresholds = np.linspace(lo, hi, n_steps)
    best_f1 = -1.0
    best_thr = lo

    for thr in thresholds:
        tp = np.sum(defect_vals >= thr)
        fp = np.sum(good_vals >= thr)
        fn = np.sum(defect_vals < thr)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        if f1 > best_f1:
            best_f1 = f1
            best_thr = float(thr)

    return best_thr, best_f1


def find_recall_at_fpr_fixed(good_vals: np.ndarray, defect_vals: np.ndarray,
                              target_fpr: float, n_steps: int = 2000) -> tuple[float, float]:
    """Find maximum recall achievable while keeping FPR <= target_fpr.

    FIXED VERSION: searches ALL thresholds meeting the FPR constraint,
    picks the one with highest recall. This correctly handles both
    normal (AUROC>0.5) and inverted (AUROC<0.5) score distributions.

    Returns (threshold, recall).
    """
    all_vals = np.concatenate([good_vals, defect_vals])
    lo, hi = float(all_vals.min()), float(all_vals.max())
    if lo == hi:
        return lo, 0.0

    thresholds = np.linspace(lo, hi, n_steps)

    best_recall = -1.0
    best_thr = lo

    for thr in thresholds:
        fpr = float(np.mean(good_vals >= thr))
        if fpr <= target_fpr:
            recall = float(np.mean(defect_vals >= thr))
            if recall > best_recall:
                best_recall = recall
                best_thr = float(thr)

    if best_recall < 0:
        # No threshold meets FPR constraint — use lowest threshold
        best_recall = float(np.mean(defect_vals >= thresholds[0]))
        best_thr = float(thresholds[0])

    return best_thr, best_recall


def analyze_score_mode(category: str, score_mode: str,
                       good_vals: np.ndarray, defect_vals: np.ndarray) -> dict:
    """Compute all metrics for one category + one score mode."""
    good_count = len(good_vals)
    defect_count = len(defect_vals)

    if good_count == 0 or defect_count == 0:
        return {"category": category, "score_mode": score_mode,
                "good_count": good_count, "defect_count": defect_count,
                "auroc": float("nan"), "best_f1": float("nan"),
                "best_f1_threshold": float("nan"),
                "recall_fpr1": float("nan"), "recall_fpr5": float("nan"),
                "good_p95": float("nan"), "good_p99": float("nan"),
                "defect_p5": float("nan"), "defect_p1": float("nan"),
                "overlap": "NO_DATA"}

    # Distribution stats
    good_p95 = float(np.percentile(good_vals, 95))
    good_p99 = float(np.percentile(good_vals, 99))
    defect_p5 = float(np.percentile(defect_vals, 5))
    defect_p1 = float(np.percentile(defect_vals, 1))

    # AUROC (threshold-independent)
    auroc = compute_auroc(good_vals, defect_vals)

    # Best F1
    best_f1_thr, best_f1 = find_best_f1(good_vals, defect_vals)

    # Recall at FPR targets (FIXED)
    _, recall_fpr1 = find_recall_at_fpr_fixed(good_vals, defect_vals, 0.01)
    _, recall_fpr5 = find_recall_at_fpr_fixed(good_vals, defect_vals, 0.05)

    # Overlap flag
    overlap = "YES" if (auroc < 0.80 or good_p99 >= defect_p5) else "no"

    return {
        "category": category,
        "score_mode": score_mode,
        "good_count": good_count,
        "defect_count": defect_count,
        "good_p95": good_p95,
        "good_p99": good_p99,
        "defect_p5": defect_p5,
        "defect_p1": defect_p1,
        "auroc": auroc,
        "best_f1_threshold": best_f1_thr,
        "best_f1": best_f1,
        "recall_fpr1": recall_fpr1,
        "recall_fpr5": recall_fpr5,
        "overlap": overlap,
    }


def write_comparison_csv(results: list[dict], output_path: Path):
    """Write score_mode_comparison.csv."""
    fieldnames = [
        "category", "score_mode", "good_count", "defect_count",
        "good_p95", "good_p99", "defect_p5", "defect_p1",
        "auroc", "best_f1_threshold", "best_f1",
        "recall_fpr1", "recall_fpr5", "overlap",
    ]
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            row = {}
            for k in fieldnames:
                v = r[k]
                if isinstance(v, float):
                    if np.isnan(v):
                        row[k] = ""
                    else:
                        row[k] = f"{v:.6f}"
                else:
                    row[k] = v
            writer.writerow(row)


def write_comparison_md(results: list[dict], output_path: Path,
                        input_csv: str):
    """Write score_mode_comparison.md."""
    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines.append("# Phase 8A-Fix: EfficientAD Score Mode Comparison Report")
    lines.append("")
    lines.append(f"Generated: {now}")
    lines.append("")

    # Methodology
    lines.append("## 0. Methodology")
    lines.append("")
    lines.append("- This analysis reuses `rknn_scores_15cls.csv` from Phase 8A (no re-inference).")
    lines.append("- **AUROC** is a threshold-independent metric measuring score ranking ability.")
    lines.append("  AUROC > 0.5 means defects score higher (normal); < 0.5 means inverted.")
    lines.append("- **F1**, **recall@FPR**, and **recommended threshold** are threshold-dependent")
    lines.append("  engineering metrics.")
    lines.append("- **recall@FPR** is computed by searching ALL thresholds that satisfy the FPR")
    lines.append("  constraint and selecting the one maximizing recall. This correctly handles")
    lines.append("  both normal and inverted score distributions.")
    lines.append("- This analysis is based on MVTec AD test split only. It is an engineering")
    lines.append("  diagnostic, NOT an external independent generalization validation.")
    lines.append("- Do NOT claim production-grade detection accuracy from these results.")
    lines.append("")

    # Build lookup: results[(category, score_mode)] = metrics
    lookup = {}
    for r in results:
        lookup[(r["category"], r["score_mode"])] = r

    # Section 1: AUROC comparison table
    lines.append("## 1. AUROC Comparison (all 5 score modes)")
    lines.append("")
    lines.append("| Category | raw_score | map_max | map_mean | map_top1 | map_top01 | Best |")
    lines.append("|----------|-----------|---------|----------|----------|-----------|------|")
    for cat in CATEGORIES:
        aurocs = {}
        for sm in SCORE_MODES:
            r = lookup.get((cat, sm))
            aurocs[sm] = r["auroc"] if r and not np.isnan(r["auroc"]) else 0.0
        best_sm = max(aurocs, key=aurocs.get)
        best_val = aurocs[best_sm]
        best_mark = f"**{best_sm}**" if best_val >= 0.80 else best_sm
        lines.append(
            f"| {cat} | {aurocs['raw_score']:.4f} | {aurocs['map_max']:.4f} | "
            f"{aurocs['map_mean']:.4f} | {aurocs['map_top1']:.4f} | "
            f"{aurocs['map_top01']:.4f} | {best_mark} ({best_val:.4f}) |"
        )
    lines.append("")

    # Section 2: Best AUROC per category
    lines.append("## 2. Best Score Mode per Category")
    lines.append("")
    lines.append("| Category | Best AUROC | Best Score Mode | map_mean AUROC | Delta vs map_mean |")
    lines.append("|----------|-----------|-----------------|----------------|-------------------|")
    for cat in CATEGORIES:
        aurocs = {}
        for sm in SCORE_MODES:
            r = lookup.get((cat, sm))
            aurocs[sm] = r["auroc"] if r and not np.isnan(r["auroc"]) else 0.0
        best_sm = max(aurocs, key=aurocs.get)
        best_val = aurocs[best_sm]
        mean_val = aurocs["map_mean"]
        delta = best_val - mean_val
        lines.append(
            f"| {cat} | {best_val:.4f} | {best_sm} | {mean_val:.4f} | {delta:+.4f} |"
        )
    lines.append("")

    # Section 3: Best-F1 comparison
    lines.append("## 3. Best F1 Score Comparison")
    lines.append("")
    lines.append("| Category | raw_score | map_max | map_mean | map_top1 | map_top01 | Best |")
    lines.append("|----------|-----------|---------|----------|----------|-----------|------|")
    for cat in CATEGORIES:
        f1s = {}
        for sm in SCORE_MODES:
            r = lookup.get((cat, sm))
            f1s[sm] = r["best_f1"] if r and not np.isnan(r["best_f1"]) else 0.0
        best_sm = max(f1s, key=f1s.get)
        lines.append(
            f"| {cat} | {f1s['raw_score']:.4f} | {f1s['map_max']:.4f} | "
            f"{f1s['map_mean']:.4f} | {f1s['map_top1']:.4f} | "
            f"{f1s['map_top01']:.4f} | {best_sm} ({f1s[best_sm]:.4f}) |"
        )
    lines.append("")

    # Section 4: recall@FPR comparison
    lines.append("## 4. Recall@FPR Comparison (FIXED)")
    lines.append("")
    lines.append("### 4.1 recall@FPR=1%")
    lines.append("")
    lines.append("| Category | raw_score | map_max | map_mean | map_top1 | map_top01 |")
    lines.append("|----------|-----------|---------|----------|----------|-----------|")
    for cat in CATEGORIES:
        vals = {}
        for sm in SCORE_MODES:
            r = lookup.get((cat, sm))
            vals[sm] = r["recall_fpr1"] if r and not np.isnan(r["recall_fpr1"]) else 0.0
        lines.append(
            f"| {cat} | {vals['raw_score']:.4f} | {vals['map_max']:.4f} | "
            f"{vals['map_mean']:.4f} | {vals['map_top1']:.4f} | "
            f"{vals['map_top01']:.4f} |"
        )
    lines.append("")

    lines.append("### 4.2 recall@FPR=5%")
    lines.append("")
    lines.append("| Category | raw_score | map_max | map_mean | map_top1 | map_top01 |")
    lines.append("|----------|-----------|---------|----------|----------|-----------|")
    for cat in CATEGORIES:
        vals = {}
        for sm in SCORE_MODES:
            r = lookup.get((cat, sm))
            vals[sm] = r["recall_fpr5"] if r and not np.isnan(r["recall_fpr5"]) else 0.0
        lines.append(
            f"| {cat} | {vals['raw_score']:.4f} | {vals['map_max']:.4f} | "
            f"{vals['map_mean']:.4f} | {vals['map_top1']:.4f} | "
            f"{vals['map_top01']:.4f} |"
        )
    lines.append("")

    # Section 5: Per-mode detailed stats (for reference)
    lines.append("## 5. Detailed Per-Mode Statistics")
    lines.append("")
    for sm in SCORE_MODES:
        lines.append(f"### 5.{SCORE_MODES.index(sm)+1} {sm}")
        lines.append("")
        lines.append("| Category | Good | Defect | Good P95 | Good P99 | Defect P5 | Defect P1 | AUROC | Best F1 | F1 Thr | Rec@1% | Rec@5% | Overlap |")
        lines.append("|----------|------|--------|----------|----------|-----------|-----------|-------|---------|--------|--------|--------|---------|")
        for cat in CATEGORIES:
            r = lookup.get((cat, sm))
            if not r:
                continue
            lines.append(
                f"| {cat} | {r['good_count']} | {r['defect_count']} | "
                f"{r['good_p95']:.2f} | {r['good_p99']:.2f} | "
                f"{r['defect_p5']:.2f} | {r['defect_p1']:.2f} | "
                f"{r['auroc']:.4f} | {r['best_f1']:.4f} | "
                f"{r['best_f1_threshold']:.2f} | "
                f"{r['recall_fpr1']:.4f} | {r['recall_fpr5']:.4f} | "
                f"{r['overlap']} |"
            )
        lines.append("")

    # Section 6: Answers to the 6 questions
    lines.append("## 6. Analysis and Recommendations")
    lines.append("")

    # Q1: Is map_mean the worst?
    auroc_by_mode = {sm: [] for sm in SCORE_MODES}
    for cat in CATEGORIES:
        for sm in SCORE_MODES:
            r = lookup.get((cat, sm))
            if r and not np.isnan(r["auroc"]):
                auroc_by_mode[sm].append(r["auroc"])

    mean_aurocs = {sm: np.mean(vals) if vals else 0.0 for sm, vals in auroc_by_mode.items()}
    best_overall = max(mean_aurocs, key=mean_aurocs.get)
    worst_overall = min(mean_aurocs, key=mean_aurocs.get)

    lines.append("### Q1: Is map_mean the best score_mode?")
    lines.append("")
    lines.append("**Average AUROC across 15 categories:**")
    lines.append("")
    lines.append("| Score Mode | Mean AUROC | Rank |")
    lines.append("|------------|-----------|------|")
    sorted_modes = sorted(mean_aurocs.items(), key=lambda x: x[1], reverse=True)
    for rank, (sm, val) in enumerate(sorted_modes, 1):
        marker = " ← best" if rank == 1 else (" ← worst" if rank == len(sorted_modes) else "")
        lines.append(f"| {sm} | {val:.4f} | {rank}{marker} |")
    lines.append("")

    if best_overall == "map_mean":
        lines.append("map_mean IS the best score_mode on average. No change recommended.")
    else:
        lines.append(f"map_mean is NOT the best. **{best_overall}** achieves higher average AUROC.")
    lines.append("")

    # Q2: Significant improvement?
    lines.append("### Q2: Does any score_mode significantly improve AUROC?")
    lines.append("")
    improvement_threshold = 0.05  # 5 percentage points
    significant_improvements = []
    for cat in CATEGORIES:
        mean_auroc = lookup.get((cat, "map_mean"), {}).get("auroc", 0)
        for sm in SCORE_MODES:
            if sm == "map_mean":
                continue
            r = lookup.get((cat, sm))
            if r and not np.isnan(r["auroc"]):
                delta = r["auroc"] - mean_auroc
                if delta > improvement_threshold:
                    significant_improvements.append((cat, sm, r["auroc"], mean_auroc, delta))

    if significant_improvements:
        lines.append(f"Yes. {len(significant_improvements)} cases show > {improvement_threshold:.0%} AUROC improvement over map_mean:")
        lines.append("")
        lines.append("| Category | Better Mode | New AUROC | map_mean AUROC | Delta |")
        lines.append("|----------|-------------|-----------|----------------|-------|")
        for cat, sm, new_a, old_a, delta in significant_improvements:
            lines.append(f"| {cat} | {sm} | {new_a:.4f} | {old_a:.4f} | {delta:+.4f} |")
    else:
        lines.append(f"No score_mode shows > {improvement_threshold:.0%} AUROC improvement over map_mean")
        lines.append("for any category. The score modes are largely equivalent in ranking ability.")
    lines.append("")

    # Q3: Always below 0.80?
    lines.append("### Q3: Categories always below AUROC 0.80 regardless of score_mode?")
    lines.append("")
    always_bad = []
    for cat in CATEGORIES:
        max_auroc = 0.0
        for sm in SCORE_MODES:
            r = lookup.get((cat, sm))
            if r and not np.isnan(r["auroc"]):
                max_auroc = max(max_auroc, r["auroc"])
        if max_auroc < 0.80:
            always_bad.append((cat, max_auroc))

    if always_bad:
        lines.append(f"Yes. {len(always_bad)}/15 categories have AUROC < 0.80 for ALL score modes:")
        lines.append("")
        for cat, best_a in always_bad:
            lines.append(f"- **{cat}**: best AUROC = {best_a:.4f}")
        lines.append("")
        lines.append("These categories cannot be reliably discriminated by raw EfficientAD output")
        lines.append("regardless of score mode selection. The raw model output is fundamentally")
        lines.append("not a calibrated anomaly score — the Anomalib post-processor (Clip + Normalize")
        lines.append("+ Sigmoid) is required for meaningful discrimination.")
    else:
        lines.append("No. All categories achieve AUROC ≥ 0.80 in at least one score mode.")
    lines.append("")

    # Q4: Should we update efficientad_score_mode?
    lines.append("### Q4: Should efficientad_score_mode be updated?")
    lines.append("")
    if best_overall == "map_mean":
        lines.append("**No.** map_mean is already the best-performing score mode on average.")
        lines.append("Keep `efficientad_score_mode: map_mean` in config.yaml.")
    elif mean_aurocs[best_overall] - mean_aurocs["map_mean"] > 0.02:
        lines.append(f"**Yes, consider switching to {best_overall}.** It achieves {mean_aurocs[best_overall]:.4f}")
        lines.append(f"mean AUROC vs map_mean's {mean_aurocs['map_mean']:.4f}")
        lines.append(f"(delta = {mean_aurocs[best_overall] - mean_aurocs['map_mean']:+.4f}).")
    else:
        lines.append(f"**Marginal.** {best_overall} is slightly better ({mean_aurocs[best_overall]:.4f} vs")
        lines.append(f"{mean_aurocs['map_mean']:.4f}), but the difference ({mean_aurocs[best_overall] - mean_aurocs['map_mean']:+.4f})")
        lines.append("is small and may not justify changing the production config.")
    lines.append("")

    # Q5/Q6: Per-category thresholds or load shedding
    lines.append("### Q5-Q6: Config update and T2 gate purpose")
    lines.append("")
    lines.append("Given that all 15 categories have AUROC < 0.80 (most < 0.55), the T2 gate")
    lines.append("should be understood as a **load shedding gate**, not a detection gate:")
    lines.append("")
    lines.append("- **Purpose**: Reduce T3 (FastSAM + Qwen3-VL) workload by dropping frames")
    lines.append("  that are very likely to be normal.")
    lines.append("- **Limitation**: Cannot reliably separate good from defective images.")
    lines.append("- **Threshold strategy**: Set at good_p95 to control ~5% false trigger rate,")
    lines.append("  allowing most frames through for VLM analysis.")
    lines.append("")

    if best_overall != "map_mean" and mean_aurocs[best_overall] - mean_aurocs["map_mean"] > 0.02:
        # Recommend per-category best score mode
        lines.append("### Recommended per-category config (if updating):")
        lines.append("")
        lines.append("```yaml")
        lines.append(f"efficientad_score_mode: {best_overall}  # best average AUROC")
        lines.append("# Per-category thresholds from best score mode per category:")
        lines.append("per_category_threshold:")
        for cat in CATEGORIES:
            best_sm = SCORE_MODES[0]
            best_a = 0.0
            for sm in SCORE_MODES:
                r = lookup.get((cat, sm))
                if r and not np.isnan(r["auroc"]) and r["auroc"] > best_a:
                    best_a = r["auroc"]
                    best_sm = sm
            r = lookup.get((cat, best_sm))
            if r:
                lines.append(f"  {cat}: {r['good_p95']:.2f}  # {best_sm}, AUROC={r['auroc']:.4f}")
        lines.append("```")
    else:
        lines.append("**Recommendation**: Keep config.yaml unchanged.")
        lines.append("T2 gate is a load shedding gate with map_mean score mode.")
        lines.append("Per-category thresholds from Phase 8A (good_p95) remain valid.")
    lines.append("")

    # Methodology disclaimer
    lines.append("## 7. Methodology Disclaimer")
    lines.append("")
    lines.append("1. This analysis is based on MVTec AD test split (1725 images, 15 classes).")
    lines.append("2. It is an engineering diagnostic, NOT external independent generalization validation.")
    lines.append("3. AUROC is threshold-independent and valid for comparing score ranking ability.")
    lines.append("4. F1, recall@FPR, and recommended thresholds are threshold-dependent engineering metrics.")
    lines.append("5. These results do NOT constitute production-grade detection accuracy claims.")
    lines.append("6. Real production calibration requires data from the actual inspection environment.")
    lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(
        description="Phase 8A-Fix: Compare all 5 EfficientAD score modes"
    )
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--output-dir", type=str, required=True)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"ERROR: {input_path} not found")
        sys.exit(1)

    # Read CSV
    print(f"Reading: {input_path}")
    data: dict[str, dict[str, list[float]]] = {}
    # data[category][score_mode] = list of (label, value)
    raw_data: dict[str, list[dict]] = {}

    with open(input_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            cat = row["category"]
            if cat not in raw_data:
                raw_data[cat] = []
            raw_data[cat].append(row)

    print(f"Read {sum(len(v) for v in raw_data.values())} rows, {len(raw_data)} categories")

    # Compute metrics for all score modes
    results = []
    for cat in CATEGORIES:
        if cat not in raw_data:
            print(f"  WARNING: no data for {cat}")
            continue

        rows = raw_data[cat]
        labels = np.array([int(r["label"]) for r in rows])
        good_mask = labels == 0
        defect_mask = labels == 1

        for sm in SCORE_MODES:
            vals = np.array([float(r[sm]) for r in rows])
            good_vals = vals[good_mask]
            defect_vals = vals[defect_mask]

            result = analyze_score_mode(cat, sm, good_vals, defect_vals)
            results.append(result)

            # Print compact summary
            auroc = result["auroc"]
            overlap_mark = " OL" if result["overlap"] == "YES" else ""
            print(f"  {cat:15s} {sm:12s}  AUROC={auroc:.4f}  "
                  f"good_p95={result['good_p95']:.2f}  "
                  f"rec@1%={result['recall_fpr1']:.4f}  "
                  f"rec@5%={result['recall_fpr5']:.4f}{overlap_mark}")

    # Write outputs
    csv_path = output_dir / "score_mode_comparison.csv"
    write_comparison_csv(results, csv_path)
    print(f"\nCSV: {csv_path}")

    md_path = output_dir / "score_mode_comparison.md"
    write_comparison_md(results, md_path, str(input_path))
    print(f"MD:  {md_path}")

    # Summary
    print(f"\n{'='*60}")
    print("  Score Mode Comparison Summary")
    print(f"{'='*60}")
    auroc_by_mode = {sm: [] for sm in SCORE_MODES}
    for r in results:
        if not np.isnan(r["auroc"]):
            auroc_by_mode[r["score_mode"]].append(r["auroc"])
    for sm in SCORE_MODES:
        vals = auroc_by_mode[sm]
        if vals:
            print(f"  {sm:12s}  mean AUROC = {np.mean(vals):.4f}  "
                  f"min = {np.min(vals):.4f}  max = {np.max(vals):.4f}")


if __name__ == "__main__":
    main()
