#!/usr/bin/env python3
"""One-shot per-sample diff analysis: 2B_lora vs 4B_lora.

Reads two JSONL files, aligns by image basename, compares
category_exact / defect_type_exact / bbox_iou_at_0_5 across
quadrants, and writes results/lora_diff_analysis.md.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS = PROJECT_ROOT / "results"
JSONL_2B = RESULTS / "ab_eval_predictions_2B_2B_lora_deployment.jsonl"
JSONL_4B = RESULTS / "ab_eval_predictions_4B_4B_lora_deployment.jsonl"
OUTPUT_MD = RESULTS / "lora_diff_analysis.md"

METRICS = ["category_exact", "defect_type_exact", "bbox_iou_at_0_5"]
METRIC_LABELS = {
    "category_exact": "Category Exact Match",
    "defect_type_exact": "Defect Type Exact Match",
    "bbox_iou_at_0_5": "BBox IoU >= 0.5",
}


def load_jsonl(path: Path) -> dict[str, dict]:
    """Load JSONL into {category/basename: record} dict."""
    records = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        key = f"{r['category']}/{Path(r['image']).name}"
        records[key] = r
    return records


def is_ok(record: dict | None, metric: str) -> bool:
    """Check if a record passes a metric. Missing/parse-fail => False."""
    if record is None:
        return False
    return record.get("metrics", {}).get(metric, False)


def is_truncated(record: dict | None) -> bool:
    if record is None:
        return False
    return record.get("output_tokens", 0) >= 200


def pred_defect_type(record: dict | None) -> str:
    if record is None:
        return "(missing)"
    pj = record.get("prediction_json")
    if pj and isinstance(pj, dict):
        return pj.get("defect_type", "(none)")
    return "(parse_fail)"


def main():
    r2 = load_jsonl(JSONL_2B)
    r4 = load_jsonl(JSONL_4B)
    all_keys = sorted(set(r2) | set(r4))

    # Quadrant counts per metric: (both_ok, only4b, only2b, neither)
    quad_counts: dict[str, dict[str, int]] = {
        m: {"both_ok": 0, "only_4b": 0, "only_2b": 0, "neither": 0}
        for m in METRICS
    }
    # Truncated breakdown per metric
    trunc_counts: dict[str, dict[str, int]] = {
        m: {"both_ok": 0, "only_4b": 0, "only_2b": 0, "neither": 0}
        for m in METRICS
    }

    # "neither" samples (defect_type) grouped by category
    neither_dt: list[dict] = []
    # "only_4b" samples (defect_type) grouped by category
    only4b_dt: list[dict] = []

    for key in all_keys:
        a = r2.get(key)  # 2B
        b = r4.get(key)  # 4B
        category = (a or b).get("category", "?")
        gt_dt = (a or b).get("gt", {}).get("defect_type", "?")
        img_name = Path(key).name  # basename for display
        a_trunc = is_truncated(a)
        b_trunc = is_truncated(b)
        any_trunc = a_trunc or b_trunc

        for m in METRICS:
            a_ok = is_ok(a, m)
            b_ok = is_ok(b, m)

            if a_ok and b_ok:
                bucket = "both_ok"
            elif a_ok and not b_ok:
                bucket = "only_2b"
            elif not a_ok and b_ok:
                bucket = "only_4b"
            else:
                bucket = "neither"

            quad_counts[m][bucket] += 1
            if any_trunc:
                trunc_counts[m][bucket] += 1

        # Collect defect_type "neither" detail rows
        a_dt_ok = is_ok(a, "defect_type_exact")
        b_dt_ok = is_ok(b, "defect_type_exact")
        if not a_dt_ok and not b_dt_ok:
            neither_dt.append({
                "category": category,
                "image": img_name,
                "gt_defect_type": gt_dt,
                "pred_2b": pred_defect_type(a),
                "pred_4b": pred_defect_type(b),
                "max_iou_2b": round(a.get("max_iou", 0), 4) if a else 0,
                "max_iou_4b": round(b.get("max_iou", 0), 4) if b else 0,
                "truncated": any_trunc,
            })

        # Collect defect_type "only_4b" detail rows
        if not a_dt_ok and b_dt_ok:
            only4b_dt.append({
                "category": category,
                "image": img_name,
                "gt_defect_type": gt_dt,
                "pred_2b": pred_defect_type(a),
                "pred_4b": pred_defect_type(b),
                "truncated": any_trunc,
            })

    # ── Build Markdown ──────────────────────────────────────────────
    lines: list[str] = []
    w = lines.append

    w("# 2B_lora vs 4B_lora Per-Sample Diff Analysis\n")
    w(f"- Source 2B: `{JSONL_2B.name}` ({len(r2)} samples)")
    w(f"- Source 4B: `{JSONL_4B.name}` ({len(r4)} samples)")
    w(f"- Aligned samples: {len(all_keys)}\n")

    # ── Section 1: Quadrant tables ──────────────────────────────────
    w("## 1. Four-Quadrant Statistics\n")
    w("| Metric | Both Correct | 2B Wrong 4B Correct | 2B Correct 4B Wrong | Both Wrong |")
    w("|--------|-------------|---------------------|---------------------|------------|")

    for m in METRICS:
        q = quad_counts[m]
        t = trunc_counts[m]
        label = METRIC_LABELS[m]
        w(f"| **{label}** | {q['both_ok']} | {q['only_4b']} | {q['only_2b']} | {q['neither']} |")

    w("")
    w("**Truncation note** (output_tokens >= 200):")
    w("")
    for m in METRICS:
        t = trunc_counts[m]
        total_trunc = sum(t.values())
        if total_trunc > 0:
            detail = ", ".join(f"{k}={v}" for k, v in t.items() if v > 0)
            w(f"- {METRIC_LABELS[m]}: {total_trunc} truncated samples ({detail})")
    w("")
    w("Truncated samples are counted in the quadrant table above but flagged separately — ")
    w("their failures may be caused by output cutoff rather than model capability.\n")

    # ── Section 2: "Both wrong" detail (defect_type) ────────────────
    w("## 2. Both Wrong Samples (defect_type_exact)\n")
    if neither_dt:
        # Group by category
        by_cat: dict[str, list[dict]] = defaultdict(list)
        for row in neither_dt:
            by_cat[row["category"]].append(row)

        for cat in sorted(by_cat):
            rows = by_cat[cat]
            w(f"### {cat} ({len(rows)} samples)\n")
            w("| Image | GT defect_type | 2B prediction | 4B prediction | 2B IoU | 4B IoU | Truncated |")
            w("|-------|---------------|---------------|---------------|--------|--------|-----------|")
            for r in rows:
                trunc_flag = "Y" if r["truncated"] else ""
                w(f"| {r['image']} | {r['gt_defect_type']} | {r['pred_2b']} | {r['pred_4b']} | {r['max_iou_2b']} | {r['max_iou_4b']} | {trunc_flag} |")
            w("")
    else:
        w("No samples where both models fail on defect_type_exact.\n")

    # ── Section 3: "2B wrong, 4B correct" detail (defect_type) ──────
    w("## 3. 2B Wrong but 4B Correct Samples (defect_type_exact)\n")
    if only4b_dt:
        by_cat2: dict[str, list[dict]] = defaultdict(list)
        for row in only4b_dt:
            by_cat2[row["category"]].append(row)

        for cat in sorted(by_cat2):
            rows = by_cat2[cat]
            w(f"### {cat} ({len(rows)} samples)\n")
            w("| Image | GT defect_type | 2B prediction | 4B prediction | Truncated |")
            w("|-------|---------------|---------------|---------------|-----------|")
            for r in rows:
                trunc_flag = "Y" if r["truncated"] else ""
                w(f"| {r['image']} | {r['gt_defect_type']} | {r['pred_2b']} | {r['pred_4b']} | {trunc_flag} |")
            w("")
    else:
        w("No samples where 2B fails but 4B succeeds on defect_type_exact.\n")

    # ── Section 4: Truncation summary ───────────────────────────────
    w("## 4. Truncation Summary\n")
    total_trunc_2b = sum(1 for r in r2.values() if is_truncated(r))
    total_trunc_4b = sum(1 for r in r4.values() if is_truncated(r))
    w(f"- 2B_lora truncated samples (output_tokens >= 200): **{total_trunc_2b}**")
    w(f"- 4B_lora truncated samples (output_tokens >= 200): **{total_trunc_4b}**")
    w("")

    # Per-category truncation
    trunc_by_cat: dict[str, dict[str, int]] = defaultdict(lambda: {"2B": 0, "4B": 0})
    for r in r2.values():
        if is_truncated(r):
            trunc_by_cat[r["category"]]["2B"] += 1
    for r in r4.values():
        if is_truncated(r):
            trunc_by_cat[r["category"]]["4B"] += 1

    if trunc_by_cat:
        w("| Category | 2B truncated | 4B truncated |")
        w("|----------|-------------|-------------|")
        for cat in sorted(trunc_by_cat):
            t = trunc_by_cat[cat]
            w(f"| {cat} | {t['2B']} | {t['4B']} |")
        w("")

    OUTPUT_MD.write_text("\n".join(lines))
    print(f"Written: {OUTPUT_MD}")
    print(f"  Total aligned samples: {len(all_keys)}")
    for m in METRICS:
        q = quad_counts[m]
        print(f"  {METRIC_LABELS[m]}: both={q['both_ok']}, 4b_only={q['only_4b']}, 2b_only={q['only_2b']}, neither={q['neither']}")


if __name__ == "__main__":
    main()
