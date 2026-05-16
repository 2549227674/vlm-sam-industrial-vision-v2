#!/usr/bin/env python3
"""Phase 5 visualization: generate figures from JSONL prediction files.

Usage:
    python scripts/plot_phase5_results.py
    python scripts/plot_phase5_results.py --output-dir results/figures
"""

import argparse
import json
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    raise SystemExit("matplotlib is required: pip install matplotlib")

try:
    import numpy as np
except ImportError:
    raise SystemExit("numpy is required: pip install numpy")

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CATEGORIES = [
    "bottle", "cable", "capsule", "carpet", "grid", "hazelnut", "leather",
    "metal_nut", "pill", "screw", "tile", "toothbrush", "transistor",
    "wood", "zipper",
]

# JSONL path definitions: (variant_label, primary_path, fallback_path)
VARIANT_PATHS = {
    "2B_base_deploy": (
        "results/phase5_6_deployment/predictions/ab_eval_predictions_2B_2B_base_deployment.jsonl",
        None,
    ),
    "2B_lora_deploy": (
        "results/phase5_6_deployment/predictions/ab_eval_predictions_2B_2B_lora_deployment.jsonl",
        None,
    ),
    "4B_base_deploy": (
        "results/phase5_6_deployment/predictions/ab_eval_predictions_4B_4B_base_deployment.jsonl",
        None,
    ),
    "4B_lora_deploy": (
        "results/phase5_6_deployment/predictions/ab_eval_predictions_4B_4B_lora_deployment.jsonl",
        None,
    ),
    "2B_base_mc": (
        "results/phase5_7_method_control/predictions/ab_eval_predictions_2B_2B_base_same_prompt_method_control.jsonl",
        None,
    ),
    "2B_lora_mc": (
        "results/phase5_7_method_control/predictions/ab_eval_predictions_2B_2B_lora_same_prompt_method_control.jsonl",
        None,
    ),
    "4B_base_mc": (
        "results/phase5_7_method_control/predictions/ab_eval_predictions_4B_4B_base_same_prompt_method_control.jsonl",
        None,
    ),
    "4B_lora_mc": (
        "results/phase5_7_method_control/predictions/ab_eval_predictions_4B_4B_lora_same_prompt_method_control.jsonl",
        None,
    ),
    "2B_base_opro": (
        "results/phase5_8_opro_baseline/predictions/ab_eval_predictions_2B_base_opro_prompt.jsonl",
        "results/phase5_8_opro_baseline/ab_eval_predictions_2B_base_opro_prompt.jsonl",
    ),
}


def resolve_path(primary: str, fallback: str | None = None) -> Path | None:
    """Return primary path if it exists, else fallback, else None."""
    p = PROJECT_ROOT / primary
    if p.exists():
        return p
    if fallback:
        f = PROJECT_ROOT / fallback
        if f.exists():
            return f
    return None


def read_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file, return list of dicts."""
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def summarize_metrics(records: list[dict]) -> dict:
    """Compute aggregate metrics from per-sample records."""
    n = len(records)
    if n == 0:
        return {}
    sums = {}
    for key in ("json_parse_ok", "schema_ok", "category_exact",
                "defect_type_exact", "severity_valid", "bbox_iou_at_0_5"):
        sums[key] = sum(1 for r in records if r.get("metrics", {}).get(key, False))
    sums["total"] = n
    for key in sums:
        if key != "total":
            sums[f"{key}_rate"] = sums[key] / n * 100 if n > 0 else 0.0
    return sums


def summarize_by_category(records: list[dict], metric_key: str) -> dict[str, float]:
    """Per-category hit rate for a given metric key."""
    cat_counts: dict[str, int] = {c: 0 for c in CATEGORIES}
    cat_totals: dict[str, int] = {c: 0 for c in CATEGORIES}
    for r in records:
        cat = r.get("category", "")
        if cat not in cat_counts:
            continue
        cat_totals[cat] += 1
        if r.get("metrics", {}).get(metric_key, False):
            cat_counts[cat] += 1
    return {
        cat: (cat_counts[cat] / cat_totals[cat] if cat_totals[cat] > 0 else 0.0)
        for cat in CATEGORIES
    }


def load_variant_data(variants: list[str]) -> dict[str, list[dict]]:
    """Load JSONL data for requested variants. Skip missing with warning."""
    data = {}
    for v in variants:
        paths = VARIANT_PATHS.get(v)
        if paths is None:
            print(f"  [WARN] unknown variant: {v}")
            continue
        p = resolve_path(paths[0], paths[1])
        if p is None:
            print(f"  [WARN] missing JSONL for {v}, skipping")
            continue
        data[v] = read_jsonl(p)
    return data


# ---------------------------------------------------------------------------
# Figure 1: Cross-phase 6-variant bar chart
# ---------------------------------------------------------------------------

def plot_cross_phase_metrics(data: dict[str, list[dict]], output_dir: Path) -> None:
    """Bar chart: 6 variants x 4 metrics."""
    variants = ["2B_base_deploy", "2B_lora_deploy", "2B_base_mc",
                "2B_lora_mc", "2B_base_opro", "4B_lora_mc"]
    metrics = ["json_parse_ok", "category_exact", "defect_type_exact", "bbox_iou_at_0_5"]
    labels = ["JSON OK", "Category", "DefType", "BBox IoU>=0.5"]

    present = [v for v in variants if v in data]
    if not present:
        print("  [SKIP] fig1: no variant data available")
        return

    summaries = {v: summarize_metrics(data[v]) for v in present}

    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(present))
    width = 0.18
    colors = ["#4C72B0", "#55A868", "#C44E52", "#8172B2"]

    for i, (metric, label, color) in enumerate(zip(metrics, labels, colors)):
        vals = [summaries[v].get(f"{metric}_rate", 0.0) for v in present]
        bars = ax.bar(x + i * width, vals, width, label=label, color=color)
        for bar, val in zip(bars, vals):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                        f"{val:.1f}", ha="center", va="bottom", fontsize=7)

    ax.set_ylabel("Percentage (%)")
    ax.set_title("Phase 5: Cross-Phase Variant Comparison")
    ax.set_xticks(x + width * 1.5)
    ax.set_xticklabels(present, rotation=30, ha="right")
    ax.set_ylim(0, 110)
    ax.legend(loc="upper right")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    out = output_dir / "fig1_cross_phase_metrics.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out}")


# ---------------------------------------------------------------------------
# Figure 2: LoRA net delta (horizontal bar)
# ---------------------------------------------------------------------------

def plot_lora_delta(data: dict[str, list[dict]], output_dir: Path) -> None:
    """Horizontal bar chart: LoRA - base delta for 2B and 4B."""
    pairs = [
        ("2B", "2B_lora_mc", "2B_base_mc"),
        ("4B", "4B_lora_mc", "4B_base_mc"),
    ]
    metrics = ["category_exact", "defect_type_exact", "bbox_iou_at_0_5"]
    labels = ["Category", "DefType", "BBox IoU>=0.5"]

    rows = []
    for size, lora_v, base_v in pairs:
        if lora_v not in data or base_v not in data:
            print(f"  [WARN] fig2: missing {lora_v} or {base_v}, skipping {size}")
            continue
        s_lora = summarize_metrics(data[lora_v])
        s_base = summarize_metrics(data[base_v])
        for metric, label in zip(metrics, labels):
            delta = s_lora.get(f"{metric}_rate", 0.0) - s_base.get(f"{metric}_rate", 0.0)
            rows.append((f"{size} {label}", delta))

    if not rows:
        print("  [SKIP] fig2: no pair data available")
        return

    fig, ax = plt.subplots(figsize=(12, 6))
    y = np.arange(len(rows))
    vals = [r[1] for r in rows]
    colors = ["#55A868" if v >= 0 else "#C44E52" for v in vals]
    bars = ax.barh(y, vals, color=colors)

    for bar, val in zip(bars, vals):
        xpos = bar.get_width() + 0.5 if val >= 0 else bar.get_width() - 0.5
        ha = "left" if val >= 0 else "right"
        ax.text(xpos, bar.get_y() + bar.get_height() / 2,
                f"+{val:.1f}pp" if val >= 0 else f"{val:.1f}pp",
                ha=ha, va="center", fontsize=9)

    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows])
    ax.set_xlabel("Delta (percentage points)")
    ax.set_title("LoRA Net Contribution (same minimal prompt, Phase 5.7)")
    ax.axvline(x=0, color="black", linewidth=0.8)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    out = output_dir / "fig2_lora_delta.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out}")


# ---------------------------------------------------------------------------
# Figure 3: Per-category BBox heatmap (2B_lora vs 4B_lora)
# ---------------------------------------------------------------------------

def plot_bbox_heatmap(data: dict[str, list[dict]], output_dir: Path) -> None:
    """Heatmap: per-category bbox_iou_at_0_5 for 2B_lora_mc and 4B_lora_mc."""
    variants = ["2B_lora_mc", "4B_lora_mc"]
    present = [v for v in variants if v in data]
    if len(present) < 2:
        print("  [SKIP] fig3: need both 2B_lora_mc and 4B_lora_mc")
        return

    cat_data = {v: summarize_by_category(data[v], "bbox_iou_at_0_5") for v in present}
    matrix = np.array([[cat_data[v][c] for v in present] for c in CATEGORIES])

    fig, ax = plt.subplots(figsize=(8, 8))
    im = ax.imshow(matrix, cmap="YlGn", vmin=0, vmax=1, aspect="auto")

    ax.set_xticks(np.arange(len(present)))
    ax.set_xticklabels(present)
    ax.set_yticks(np.arange(len(CATEGORIES)))
    ax.set_yticklabels(CATEGORIES)

    for i in range(len(CATEGORIES)):
        for j in range(len(present)):
            val = matrix[i, j]
            color = "white" if val > 0.5 else "black"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", color=color, fontsize=8)

    ax.set_title("Per-Category BBox IoU>=0.5 Hit Rate")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    out = output_dir / "fig3_bbox_per_category_heatmap.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out}")


# ---------------------------------------------------------------------------
# Figure 4: max_iou distribution histogram
# ---------------------------------------------------------------------------

def plot_iou_distribution(data: dict[str, list[dict]], output_dir: Path) -> None:
    """Histogram: max_iou distribution for 2B_lora_mc and 4B_lora_mc."""
    variants = ["2B_lora_mc", "4B_lora_mc"]
    present = [v for v in variants if v in data]
    if not present:
        print("  [SKIP] fig4: no lora mc data available")
        return

    bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    fig, ax = plt.subplots(figsize=(10, 5))
    colors = ["#4C72B0", "#C44E52"]

    for v, color in zip(present, colors):
        ious = [r["max_iou"] for r in data[v] if r.get("max_iou") is not None]
        if ious:
            ax.hist(ious, bins=bins, alpha=0.6, label=v, color=color, edgecolor="black")

    ax.axvline(x=0.5, color="red", linestyle="--", linewidth=1.5, label="IoU=0.5 threshold")
    ax.set_xlabel("Max IoU")
    ax.set_ylabel("Count")
    ax.set_title("Max IoU Distribution (LoRA variants, Phase 5.7)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    out = output_dir / "fig4_iou_distribution.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out}")


# ---------------------------------------------------------------------------
# Figure 5: Ablation summary (prompt engineering vs LoRA-SFT)
# ---------------------------------------------------------------------------

def plot_ablation_summary(data: dict[str, list[dict]], output_dir: Path) -> None:
    """Line/grouped-point plot: 4 configurations across 3 task metrics."""
    configs = [
        ("2B_base + minimal (5.7)", "2B_base_mc"),
        ("2B_base + engineered (5.6)", "2B_base_deploy"),
        ("2B_base + OPRO (5.8)", "2B_base_opro"),
        ("2B_lora + minimal (5.7)", "2B_lora_mc"),
    ]
    metrics = ["category_exact", "defect_type_exact", "bbox_iou_at_0_5"]
    labels = ["Category", "DefType", "BBox IoU>=0.5"]

    # Fallback values for engineered prompt if JSONL missing
    engineered_fallback = {"category_exact": 53.1, "defect_type_exact": 11.2, "bbox_iou_at_0_5": 1.5}

    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(labels))
    markers = ["o", "s", "^", "D"]
    colors = ["#4C72B0", "#55A868", "#C44E52", "#8172B2"]

    for (name, variant), marker, color in zip(configs, markers, colors):
        if variant in data:
            s = summarize_metrics(data[variant])
            vals = [s.get(f"{m}_rate", 0.0) for m in metrics]
        elif variant == "2B_base_deploy":
            # fallback to known values
            vals = [engineered_fallback[m] for m in metrics]
            print(f"  [INFO] fig5: using fallback values for {name}")
        else:
            print(f"  [WARN] fig5: missing {variant}, skipping")
            continue
        ax.plot(x, vals, marker=marker, label=name, color=color, markersize=8, linewidth=2)
        for xi, vi in zip(x, vals):
            ax.annotate(f"{vi:.1f}", (xi, vi), textcoords="offset points",
                        xytext=(0, 8), ha="center", fontsize=7)

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Percentage (%)")
    ax.set_title("Prompt Engineering vs LoRA-SFT: Ablation Summary")
    ax.set_ylim(0, 105)
    ax.legend(loc="upper left")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    out = output_dir / "fig5_ablation_summary.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 5 visualization")
    parser.add_argument("--output-dir", type=str, default="results/figures",
                        help="Output directory for figures (default: results/figures)")
    args = parser.parse_args()

    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except OSError:
        pass

    # Load all variant data
    all_variants = list(VARIANT_PATHS.keys())
    print("Loading JSONL data...")
    data = load_variant_data(all_variants)
    print(f"Loaded {len(data)} variants: {list(data.keys())}")

    # Generate figures (each in its own try/except)
    plot_funcs = [
        ("Fig 1", lambda: plot_cross_phase_metrics(data, output_dir)),
        ("Fig 2", lambda: plot_lora_delta(data, output_dir)),
        ("Fig 3", lambda: plot_bbox_heatmap(data, output_dir)),
        ("Fig 4", lambda: plot_iou_distribution(data, output_dir)),
        ("Fig 5", lambda: plot_ablation_summary(data, output_dir)),
    ]

    for name, func in plot_funcs:
        try:
            func()
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")

    print(f"\nSaved figures to: {output_dir}")


if __name__ == "__main__":
    main()
