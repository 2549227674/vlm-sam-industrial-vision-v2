#!/usr/bin/env python3
"""Generate report charts for vlm-sam-industrial-vision-v2.

Parses CSV/JSON/Markdown tables from the repository and generates
PNG + SVG figures for documentation. No model execution, no network access.

Output: docs/figures/report_charts/
"""

import csv
import json
import re
from io import StringIO
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "figures" / "report_charts"
OUT.mkdir(parents=True, exist_ok=True)

FIG_W, FIG_H = 10, 6
DPI = 150

generated = []
skipped = []


def save(fig, stem):
    for ext in ("png", "svg"):
        p = OUT / f"{stem}.{ext}"
        fig.savefig(p, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    generated.append(stem)
    print(f"  [OK] {stem}")


def skip(stem, reason):
    skipped.append((stem, reason))
    print(f"  [SKIP] {stem}: {reason}")


# ── Helpers ──────────────────────────────────────────────────────────────

def parse_md_table(text: str, header_re: str) -> list[dict]:
    """Find a markdown table whose first header matches header_re, return rows."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(header_re, line.strip()):
            headers = [h.strip() for h in line.strip("|").split("|")]
            rows = []
            for j in range(i + 2, len(lines)):
                row_line = lines[j].strip()
                if not row_line.startswith("|"):
                    break
                vals = [v.strip() for v in row_line.strip("|").split("|")]
                rows.append(dict(zip(headers, vals)))
            return rows
    return []


def safe_float(v, default=None):
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


# ── Figure 01: Phase10 YOLO per-class mAP ───────────────────────────────

def fig01():
    src = REPO / "docs" / "experiments" / "phase10_training_run_1.md"
    if not src.exists():
        skip("fig01_phase10_yolo_per_class_map", f"{src} not found")
        return
    text = src.read_text()
    rows = parse_md_table(text, r"\|\s*Class\s*\|")
    if not rows:
        skip("fig01_phase10_yolo_per_class_map", "Cannot parse per-class table")
        return

    classes, map50, map5095, prec, recall = [], [], [], [], []
    for r in rows:
        cls = r.get("Class", "").strip()
        if cls in ("", "All") or cls.startswith("**"):
            continue
        m50 = safe_float(r.get("mAP50"))
        m5095 = safe_float(r.get("mAP50-95"))
        p = safe_float(r.get("Precision"))
        rc = safe_float(r.get("Recall"))
        if m50 is not None:
            classes.append(cls)
            map50.append(m50)
            map5095.append(m5095 or 0)
            prec.append(p or 0)
            recall.append(rc or 0)

    if not classes:
        skip("fig01_phase10_yolo_per_class_map", "No valid class data")
        return

    # Sort by mAP50 ascending
    order = np.argsort(map50)
    classes = [classes[i] for i in order]
    map50 = [map50[i] for i in order]
    map5095 = [map5095[i] for i in order]
    prec = [prec[i] for i in order]
    recall = [recall[i] for i in order]

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    y = np.arange(len(classes))
    h = 0.2
    ax.barh(y - 1.5*h, prec, h, label="Precision", color="#94a3b8")
    ax.barh(y - 0.5*h, recall, h, label="Recall", color="#60a5fa")
    ax.barh(y + 0.5*h, map50, h, label="mAP50", color="#22c55e")
    ax.barh(y + 1.5*h, map5095, h, label="mAP50-95", color="#f59e0b")

    # Highlight weak classes (mAP50 < 0.4)
    for i, (m, c) in enumerate(zip(map50, classes)):
        if m < 0.4:
            ax.barh(y[i] + 0.5*h, m, h, color="#ef4444", alpha=0.3)

    ax.set_yticks(y)
    ax.set_yticklabels(classes, fontsize=8)
    ax.set_xlabel("Score")
    ax.set_xlim(0, 1.1)
    ax.legend(loc="lower right", fontsize=8)
    ax.set_title("Phase 10: YOLOv8n Per-Class Validation\n"
                 "(metal_nut + cable, 12 classes, 185 images, best mAP50=0.593)")
    ax.axvline(0.4, color="#ef4444", ls="--", alpha=0.5, label="weak threshold")
    ax.grid(axis="x", alpha=0.3)
    save(fig, "fig01_phase10_yolo_per_class_map")


# ── Figure 02: Phase10 RKNN smoke latency ───────────────────────────────

def fig02():
    src = REPO / "docs" / "experiments" / "phase10_training_run_1.md"
    if not src.exists():
        skip("fig02_phase10_rknn_smoke_latency", f"{src} not found")
        return
    text = src.read_text()
    rows = parse_md_table(text, r"\|\s*Stage\s*\|")
    if not rows:
        skip("fig02_phase10_rknn_smoke_latency", "Cannot parse latency table")
        return

    stages, times = [], []
    for r in rows:
        stage = r.get("Stage", "").strip()
        time_s = r.get("Time", "").strip()
        if not stage or stage.startswith("**"):
            continue
        # Parse "0.1 ms" or "0.8 ms"
        m = re.search(r"([\d.]+)\s*ms", time_s)
        if m:
            stages.append(stage.replace("**", ""))
            times.append(float(m.group(1)))

    if not stages:
        skip("fig02_phase10_rknn_smoke_latency", "No valid latency data")
        return

    fig, ax = plt.subplots(figsize=(8, 4))
    colors = ["#60a5fa", "#22c55e", "#f59e0b", "#a855f7"]
    cumulative = 0
    for i, (s, t) in enumerate(zip(stages, times)):
        ax.barh(0, t, left=cumulative, height=0.5, color=colors[i % len(colors)],
                label=f"{s} ({t} ms)")
        ax.text(cumulative + t/2, 0, f"{t}", ha="center", va="center", fontsize=9,
                fontweight="bold", color="white")
        cumulative += t

    ax.set_xlim(0, cumulative * 1.2)
    ax.set_yticks([])
    ax.set_xlabel("Time (ms)")
    ax.set_title("Phase 10: RK3588 RKNN FP16 Smoke Latency Stack\n"
                 "(2 images, PASS: bbox valid 5, invalid 0)")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(axis="x", alpha=0.3)
    save(fig, "fig02_phase10_rknn_smoke_latency")


# ── Figure 03: Phase10 ORT snapshot distribution ────────────────────────

def fig03():
    src = REPO / "frontend" / "public" / "demo-data" / "phase10_ort_latest" / "defects_snapshot.json"
    if not src.exists():
        skip("fig03_phase10_ort_snapshot_distribution", f"{src} not found")
        return
    data = json.loads(src.read_text())
    items = data.get("items", [])
    if not items:
        skip("fig03_phase10_ort_snapshot_distribution", "No items in snapshot")
        return

    from collections import Counter
    cats = Counter(it["category"] for it in items)
    dtypes = Counter(it["defect_type"] for it in items)
    sevs = Counter(it["severity"] for it in items)

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))

    # Category
    ax = axes[0]
    c_labels, c_vals = zip(*cats.most_common())
    ax.bar(c_labels, c_vals, color="#60a5fa")
    ax.set_title("Category Distribution")
    ax.set_ylabel("Count")

    # Defect type
    ax = axes[1]
    d_labels, d_vals = zip(*dtypes.most_common())
    ax.barh(range(len(d_labels)), d_vals, color="#22c55e")
    ax.set_yticks(range(len(d_labels)))
    ax.set_yticklabels(d_labels, fontsize=7)
    ax.set_title("Defect Type Distribution")
    ax.set_xlabel("Count")

    # Severity
    ax = axes[2]
    s_labels, s_vals = zip(*sevs.most_common())
    colors_sev = {"low": "#86efac", "medium": "#fbbf24", "high": "#ef4444"}
    ax.bar(s_labels, s_vals, color=[colors_sev.get(s, "#94a3b8") for s in s_labels])
    ax.set_title("Severity Distribution")
    ax.set_ylabel("Count")

    fig.suptitle("Phase 10 ORT Snapshot (40 records, ORT CPU fallback, VLM NOT called)",
                 fontsize=10, y=1.02)
    fig.tight_layout()
    save(fig, "fig03_phase10_ort_snapshot_distribution")


# ── Figure 04: Phase10 ORT pipeline latency ─────────────────────────────

def fig04():
    src = REPO / "frontend" / "public" / "demo-data" / "phase10_ort_latest" / "defects_snapshot.json"
    if not src.exists():
        skip("fig04_phase10_ort_pipeline_latency", f"{src} not found")
        return
    data = json.loads(src.read_text())
    items = data.get("items", [])
    if not items:
        skip("fig04_phase10_ort_pipeline_latency", "No items")
        return

    ead_times, loc_times = [], []
    loc_pre, loc_infer, loc_post = [], [], []
    for it in items:
        pm = it.get("pipeline_ms", {})
        ead_times.append(pm.get("efficientad", 0))
        loc_times.append(pm.get("localizer", 0))
        for ev in it.get("trace_events", []):
            name = ev.get("name", "")
            dur_ms = ev.get("dur", 0) / 1000.0  # us -> ms
            if name == "localizer_preprocess":
                loc_pre.append(dur_ms)
            elif name == "localizer_infer":
                loc_infer.append(dur_ms)
            elif name == "localizer_postprocess":
                loc_post.append(dur_ms)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Boxplot: efficientad vs localizer
    ax = axes[0]
    bp = ax.boxplot([ead_times, loc_times],
                    tick_labels=["EfficientAD", "YOLOv8n ORT"],
                    patch_artist=True)
    bp["boxes"][0].set_facecolor("#dbeafe")
    bp["boxes"][1].set_facecolor("#dcfce7")
    ax.set_ylabel("Time (ms)")
    ax.set_title("Pipeline Latency Distribution")
    ax.grid(axis="y", alpha=0.3)

    # Stacked bar: localizer stages
    ax = axes[1]
    if loc_pre and loc_infer and loc_post:
        avg_pre = np.mean(loc_pre)
        avg_infer = np.mean(loc_infer)
        avg_post = np.mean(loc_post)
        stages = ["Localizer\n(avg)"]
        ax.barh(0, avg_pre, height=0.4, color="#60a5fa", label=f"preprocess ({avg_pre:.1f} ms)")
        ax.barh(0, avg_infer, height=0.4, left=avg_pre, color="#22c55e",
                label=f"infer ({avg_infer:.1f} ms)")
        ax.barh(0, avg_post, height=0.4, left=avg_pre + avg_infer, color="#f59e0b",
                label=f"postprocess ({avg_post:.1f} ms)")
        ax.set_yticks([])
        ax.set_xlabel("Time (ms)")
        ax.set_title("YOLOv8n ORT Stage Breakdown (avg)")
        ax.legend(fontsize=8)
    else:
        ax.text(0.5, 0.5, "No trace_events data", ha="center", va="center",
                transform=ax.transAxes)

    fig.suptitle("Phase 10 ORT Pipeline Latency\n"
                 "(ORT CPU fallback, NOT RKNN/NPU; VLM metrics = 0)",
                 fontsize=10, y=1.02)
    fig.tight_layout()
    save(fig, "fig04_phase10_ort_pipeline_latency")


# ── Figure 05: Phase9 vs Phase10 snapshot comparison ────────────────────

def fig05():
    p9 = REPO / "frontend" / "public" / "demo-data" / "phase9_soak_archive" / "manifest.json"
    p10 = REPO / "frontend" / "public" / "demo-data" / "phase10_ort_latest" / "manifest.json"
    if not p9.exists() or not p10.exists():
        skip("fig05_phase9_vs_phase10_snapshot_compare",
             f"Missing manifest: {p9.exists()=}, {p10.exists()=}")
        return

    m9 = json.loads(p9.read_text())
    m10 = json.loads(p10.read_text())

    labels = ["Source", "Mode", "Duration\n(min)", "Records", "Images",
              "Categories", "Variants", "Contract"]
    v9 = [
        m9.get("source", "?"),
        m9.get("mode", "?"),
        str(m9.get("duration_min", "?")),
        str(m9.get("data_counts", {}).get("records", "?")),
        str(m9.get("data_counts", {}).get("images", "?")),
        str(len(m9.get("data_counts", {}).get("categories", []))),
        str(len(m9.get("data_counts", {}).get("variants", []))),
        m9.get("contract_version", "?"),
    ]
    v10 = [
        m10.get("source", "?"),
        m10.get("mode", "?"),
        str(m10.get("duration_min", "?")),
        str(m10.get("data_counts", {}).get("records", "?")),
        str(m10.get("data_counts", {}).get("images", "?")),
        str(len(m10.get("data_counts", {}).get("categories", []))),
        str(len(m10.get("data_counts", {}).get("variants", []))),
        m10.get("contract_version", "?"),
    ]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.axis("off")
    table_data = [["Metric", "Phase 9 VLM", "Phase 10 ORT"]]
    for lb, a, b in zip(labels, v9, v10):
        table_data.append([lb, a, b])

    table = ax.table(cellText=table_data, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.4)
    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_facecolor("#1e293b")
            cell.set_text_props(color="white", fontweight="bold")
        elif col == 0:
            cell.set_facecolor("#f1f5f9")

    ax.set_title("Phase 9 vs Phase 10 Snapshot Comparison\n"
                 "(Phase 9 = VLM pipeline, Phase 10 = ORT CPU fallback, VLM NOT called)",
                 fontsize=10, pad=20)
    save(fig, "fig05_phase9_vs_phase10_snapshot_compare")


# ── Figure 06: Phase8C beat sweep pressure ──────────────────────────────

def fig06():
    src = REPO / "results" / "phase8c_beat_sweep" / "phase8c_beat_sweep_results.csv"
    if not src.exists():
        skip("fig06_phase8c_beat_sweep_pressure", f"{src} not found")
        return

    reader = csv.DictReader(src.read_text().splitlines())
    rows = list(reader)
    if not rows:
        skip("fig06_phase8c_beat_sweep_pressure", "Empty CSV")
        return

    beat_ms = [int(r["beat_ms"]) for r in rows]
    drops = [int(r["queue_drop_count"]) for r in rows]
    avg_vlm = [safe_float(r.get("avg_qwen3vl_ms", "0"), 0) for r in rows]
    vlm_ratio = [a / b if b > 0 else 0 for a, b in zip(avg_vlm, beat_ms)]
    rss = [safe_float(r.get("avg_rss_mb", "0"), 0) for r in rows]
    decode = [safe_float(r.get("avg_decode_tps", "0"), 0) for r in rows]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Left: queue drops
    colors = ["#22c55e" if d == 0 else "#ef4444" for d in drops]
    ax1.bar(range(len(beat_ms)), drops, color=colors)
    ax1.set_xticks(range(len(beat_ms)))
    ax1.set_xticklabels([f"{b}" for b in beat_ms])
    ax1.set_xlabel("beat_ms (capture interval)")
    ax1.set_ylabel("Queue Drop Count")
    ax1.set_title("Queue Drops vs Capture Interval")
    ax1.axhline(0, color="#94a3b8", ls="--", alpha=0.5)
    for i, d in enumerate(drops):
        if d > 0:
            ax1.text(i, d + 0.3, str(d), ha="center", fontsize=9, fontweight="bold")

    # Right: VLM utilization ratio
    ax2.plot(beat_ms, vlm_ratio, "o-", color="#f59e0b", linewidth=2, markersize=8)
    ax2.axhline(1.0, color="#ef4444", ls="--", alpha=0.7, label="Bottleneck (ratio=1.0)")
    ax2.fill_between(beat_ms, 1.0, max(vlm_ratio) * 1.1, alpha=0.1, color="#ef4444")
    ax2.fill_between(beat_ms, 0, 1.0, alpha=0.1, color="#22c55e")
    ax2.set_xlabel("beat_ms (capture interval)")
    ax2.set_ylabel("VLM Utilization (avg_vlm_ms / beat_ms)")
    ax2.set_title("VLM Utilization Ratio vs Capture Interval")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3)

    fig.suptitle("Phase 8C: Beat Sweep Pressure Test (pass_all worst-case)\n"
                 "Explains why VLM becomes bottleneck -> ORT YOLO / async enrichment",
                 fontsize=10, y=1.02)
    fig.tight_layout()
    save(fig, "fig06_phase8c_beat_sweep_pressure")


# ── Figure 07: EfficientAD score mode AUROC ─────────────────────────────

def fig07():
    src = REPO / "results" / "phase8_threshold_calibration" / "score_mode_comparison.csv"
    if not src.exists():
        skip("fig07_efficientad_score_mode_auroc", f"{src} not found")
        return

    reader = csv.DictReader(src.read_text().splitlines())
    rows = list(reader)
    if not rows:
        skip("fig07_efficientad_score_mode_auroc", "Empty CSV")
        return

    categories = sorted(set(r["category"] for r in rows))
    modes = ["raw_score", "map_max", "map_mean", "map_top1", "map_top01"]

    auroc_matrix = {}
    for r in rows:
        cat = r["category"]
        mode = r["score_mode"]
        auroc = safe_float(r.get("auroc", "0"), 0)
        auroc_matrix[(cat, mode)] = auroc

    data = np.zeros((len(categories), len(modes)))
    for i, cat in enumerate(categories):
        for j, mode in enumerate(modes):
            data[i, j] = auroc_matrix.get((cat, mode), 0)

    fig, ax = plt.subplots(figsize=(8, 8))
    im = ax.imshow(data, cmap="RdYlGn", vmin=0.2, vmax=1.0, aspect="auto")
    ax.set_xticks(range(len(modes)))
    ax.set_xticklabels(modes, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(categories)))
    ax.set_yticklabels(categories, fontsize=8)

    for i in range(len(categories)):
        for j in range(len(modes)):
            v = data[i, j]
            color = "white" if v < 0.5 else "black"
            ax.text(j, i, f"{v:.3f}", ha="center", va="center", fontsize=7, color=color)

    plt.colorbar(im, ax=ax, label="AUROC", shrink=0.8)
    mean_auroc = np.mean(data)
    ax.set_title(f"EfficientAD Score Mode AUROC (mean={mean_auroc:.3f})\n"
                 "All modes < 0.85 for most categories — gate, not detector",
                 fontsize=10)
    fig.tight_layout()
    save(fig, "fig07_efficientad_score_mode_auroc")


# ── Figure 08: VLM quantization cliff ───────────────────────────────────

def fig08():
    src = REPO / "results" / "phase8_vlm_ab" / "board_2b_base_ab_v2_results.csv"
    if not src.exists():
        skip("fig08_vlm_quantization_cliff", f"{src} not found")
        return

    # We'll construct the comparison from known data:
    # PC bf16 (from deployment benchmark) vs Board W8A8 (from AB v2)
    # Using hardcoded values from docs/experiments/phase5_6_deployment_benchmark_report.md
    # and board_2b_base_ab_v2_summary.md

    metrics = ["JSON OK", "Schema Valid", "Category\nExact", "DefectType\nExact", "BBox\nIoU>=0.5"]
    # PC 2B base bf16 (409 samples)
    pc_vals = [96.1, 96.1, 95.1, 51.8, 47.7]
    # Board 2B base W8A8 (14 samples)
    board_vals = [92.9, 92.9, 92.9, 0.0, 0.0]

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(metrics))
    w = 0.35
    bars1 = ax.bar(x - w/2, pc_vals, w, label="PC RTX 4090 bf16 (n=409)", color="#60a5fa")
    bars2 = ax.bar(x + w/2, board_vals, w, label="Board RK3588 W8A8 (n=14)", color="#ef4444")

    # Highlight quantization cliff region
    for i in range(2, 5):
        ax.axvspan(i - 0.4, i + 0.4, alpha=0.1, color="#ef4444")

    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=9)
    ax.set_ylabel("Score (%)")
    ax.set_ylim(0, 110)
    ax.legend(fontsize=9)
    ax.set_title("VLM Quantization Cliff: PC bf16 vs Board W8A8\n"
                 "W8A8 preserves coarse fields but destroys fine-grained defect_type/bbox",
                 fontsize=10)
    ax.grid(axis="y", alpha=0.3)

    for bar in bars1:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f"{bar.get_height():.1f}%", ha="center", fontsize=8)
    for bar in bars2:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f"{bar.get_height():.1f}%", ha="center", fontsize=8)

    fig.tight_layout()
    save(fig, "fig08_vlm_quantization_cliff")


# ── Main ────────────────────────────────────────────────────────────────

def write_manifest():
    """Write chart_sources_manifest.md."""
    manifest = REPO / "docs" / "reports" / "chart_sources_manifest.md"
    lines = [
        "# Chart Sources Manifest",
        "",
        "> Auto-generated by scripts/plot_report_charts.py",
        "",
        "| Figure ID | Output File | Source Files | Claim Supported | Claim Not Supported |",
        "|-----------|-------------|-------------|-----------------|---------------------|",
    ]
    for stem in generated:
        src_map = {
            "fig01_phase10_yolo_per_class_map": (
                "docs/experiments/phase10_training_run_1.md",
                "Phase 10 YOLOv8n per-class validation",
                "Not real production mAP; curated metal_nut+cable only",
            ),
            "fig02_phase10_rknn_smoke_latency": (
                "docs/experiments/phase10_training_run_1.md",
                "Phase 10 RKNN FP16 smoke latency stack",
                "2 images only, not full benchmark",
            ),
            "fig03_phase10_ort_snapshot_distribution": (
                "frontend/public/demo-data/phase10_ort_latest/defects_snapshot.json",
                "Phase 10 ORT snapshot distribution",
                "ORT CPU fallback; VLM NOT called",
            ),
            "fig04_phase10_ort_pipeline_latency": (
                "frontend/public/demo-data/phase10_ort_latest/defects_snapshot.json",
                "Phase 10 ORT pipeline latency",
                "ORT CPU fallback, NOT RKNN/NPU",
            ),
            "fig05_phase9_vs_phase10_snapshot_compare": (
                "frontend/public/demo-data/phase9_soak_archive/manifest.json, phase10_ort_latest/manifest.json",
                "Phase 9 vs 10 system evolution comparison",
                "Not model leaderboard; Phase10 VLM NOT called",
            ),
            "fig06_phase8c_beat_sweep_pressure": (
                "results/phase8c_beat_sweep/phase8c_beat_sweep_results.csv",
                "VLM bottleneck under pressure",
                "pass_all worst-case; not threshold deployment",
            ),
            "fig07_efficientad_score_mode_auroc": (
                "results/phase8_threshold_calibration/score_mode_comparison.csv",
                "EfficientAD as load-shedding gate",
                "Not a reliable detector; most AUROC < 0.85",
            ),
            "fig08_vlm_quantization_cliff": (
                "results/phase8_vlm_ab/board_2b_base_ab_v2_results.csv",
                "W8A8 quantization cliff for fine-grained fields",
                "Not claiming VLM production deployment",
            ),
        }
        s, claim, caveat = src_map.get(stem, ("?", "?", "?"))
        lines.append(
            f"| `{stem}` | `docs/figures/report_charts/{stem}.png` | {s} | {claim} | {caveat} |"
        )
    for stem, reason in skipped:
        lines.append(
            f"| `{stem}` | SKIPPED | — | — | {reason} |"
        )
    manifest.write_text("\n".join(lines) + "\n")
    print(f"\n  Manifest written: {manifest}")


def write_captions():
    """Write chart_caption_bank.md."""
    captions = REPO / "docs" / "reports" / "chart_caption_bank.md"
    entries = {
        "fig01_phase10_yolo_per_class_map": {
            "caption": "Phase 10 YOLOv8n per-class validation: metal_nut + cable (12 classes, 185 images). "
                       "Best mAP50=0.593. Weak classes: cut_outer_insulation (0.239), poke_insulation (0.287), "
                       "combined (0.338). Strong: flip (0.995), missing_cable (0.995).",
            "readme": "Yes — in Technical Highlights or Limitations section",
            "portfolio": "Yes — in Experiment Results section",
            "boundary": "Curated 12-class subset, not full MVTec 15-class. Not real production mAP.",
        },
        "fig02_phase10_rknn_smoke_latency": {
            "caption": "RK3588 RKNN FP16 smoke latency: preprocess 37.8ms + inference 95.2ms + postprocess 3.7ms = 136.7ms total.",
            "readme": "Yes — in Edge Pipeline section",
            "portfolio": "Yes — as latency evidence",
            "boundary": "2-image smoke test, not full deployment benchmark.",
        },
        "fig03_phase10_ort_snapshot_distribution": {
            "caption": "Phase 10 ORT snapshot: 40 records, cable + metal_nut categories, ORT CPU fallback.",
            "readme": "Yes — in Evidence Snapshot",
            "portfolio": "Yes — in ORT localizer section",
            "boundary": "ORT CPU fallback, NOT RKNN/NPU. VLM NOT called. Only metal_nut + cable.",
        },
        "fig04_phase10_ort_pipeline_latency": {
            "caption": "Phase 10 ORT pipeline latency: EfficientAD ~350ms, YOLOv8n ORT ~188ms.",
            "readme": "Optional",
            "portfolio": "Yes",
            "boundary": "ORT CPU fallback. VLM metrics = 0 (not called).",
        },
        "fig05_phase9_vs_phase10_snapshot_compare": {
            "caption": "Phase 9 (VLM pipeline, 30.2min soak) vs Phase 10 (ORT CPU, 27min soak) system evolution.",
            "readme": "Yes — in Deployment Tracks section",
            "portfolio": "Yes — as evolution narrative",
            "boundary": "Comparison is system evolution, not model leaderboard. Phase 10 VLM NOT called.",
        },
        "fig06_phase8c_beat_sweep_pressure": {
            "caption": "Phase 8C beat sweep: VLM utilization crosses 1.0 bottleneck at ~10000ms. "
                       "At 5000ms, 23 queue drops accumulate.",
            "readme": "Yes — explains ORT YOLO motivation",
            "portfolio": "Yes — in engineering trade-offs",
            "boundary": "pass_all worst-case. Not threshold deployment traffic.",
        },
        "fig07_efficientad_score_mode_auroc": {
            "caption": "EfficientAD 15-class score mode AUROC heatmap. Mean AUROC=0.510. "
                       "All 5 score modes nearly identical. Only tile/carpet > 0.7.",
            "readme": "Yes — in Engineering Evidence section",
            "portfolio": "Yes — in EfficientAD gate justification",
            "boundary": "EfficientAD is a load-shedding gate, not a reliable detector.",
        },
        "fig08_vlm_quantization_cliff": {
            "caption": "W8A8 quantization cliff: PC bf16 defect_type_exact=51.8%, Board W8A8=0%. "
                       "Coarse fields preserved, fine-grained collapsed.",
            "readme": "Yes — in Engineering Evidence section",
            "portfolio": "Yes — in quantization diagnostics",
            "boundary": "Supports engineering decision; does not claim VLM production deployment.",
        },
    }
    lines = ["# Chart Caption Bank", "", "> Auto-generated by scripts/plot_report_charts.py", ""]
    for stem, info in entries.items():
        if stem in generated:
            lines.append(f"## {stem}")
            lines.append("")
            lines.append(f"**Caption**: {info['caption']}")
            lines.append(f"**Use in README**: {info['readme']}")
            lines.append(f"**Use in portfolio**: {info['portfolio']}")
            lines.append(f"**Boundary**: {info['boundary']}")
            lines.append("")
    captions.write_text("\n".join(lines) + "\n")
    print(f"  Captions written: {captions}")


def main():
    print("Generating report charts...")
    print()
    fig01()
    fig02()
    fig03()
    fig04()
    fig05()
    fig06()
    fig07()
    fig08()
    print()
    write_manifest()
    write_captions()
    print(f"\nGenerated {len(generated)} figures.")
    print(f"Skipped {len(skipped)} figures.")
    for stem, reason in skipped:
        print(f"  - {stem}: {reason}")


if __name__ == "__main__":
    main()
