#!/usr/bin/env python3
"""Compute defect_group_exact rates with alias grouping.

Reads 4 per-sample JSONL files, applies defect_type alias groups,
and outputs a Markdown comparison of defect_type_exact vs defect_group_exact.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS = PROJECT_ROOT / "results"
OUTPUT_MD = RESULTS / "defect_group_analysis.md"

JSONL_FILES = {
    "2B_base": RESULTS / "ab_eval_predictions_2B_2B_base_deployment.jsonl",
    "2B_lora": RESULTS / "ab_eval_predictions_2B_2B_lora_deployment.jsonl",
    "4B_base": RESULTS / "ab_eval_predictions_4B_4B_base_deployment.jsonl",
    "4B_lora": RESULTS / "ab_eval_predictions_4B_4B_lora_deployment.jsonl",
}

# Alias groups: category -> group_name -> set of defect_types
ALIAS_GROUPS: dict[str, dict[str, set[str]]] = {
    "screw": {
        "screw_thread": {"thread_top", "thread_side"},
        "screw_scratch": {"scratch_head", "scratch_neck"},
        "manipulation": {"manipulated_front"},
    },
    "zipper": {
        "fabric_defect": {"fabric_border", "fabric_interior", "fabric_front"},
        "teeth_defect": {"broken_teeth", "split_teeth", "squeezed_teeth", "rough"},
    },
    "cable": {
        "insulation_defect": {"cut_inner_insulation", "cut_outer_insulation", "poke_insulation"},
        "wire_defect": {"bent_wire", "missing_wire", "cut_wire"},
    },
    "capsule": {
        "surface_scratch_crack": {"crack", "scratch"},
    },
    "pill": {
        "surface_scratch_crack": {"crack", "scratch"},
    },
    "carpet": {
        "opening_defect": {"cut", "hole"},
    },
}

# Build reverse lookup: (category, defect_type) -> group_name
_REVERSE: dict[tuple[str, str], str] = {}
for cat, groups in ALIAS_GROUPS.items():
    for group_name, dtypes in groups.items():
        for dt in dtypes:
            _REVERSE[(cat, dt)] = group_name


def get_group(category: str, defect_type: str) -> str | None:
    return _REVERSE.get((category, defect_type))


def load_jsonl(path: Path) -> list[dict]:
    records = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))
    return records


def compute_rates(records: list[dict]) -> dict:
    """Compute defect_type_exact and defect_group_exact rates."""
    total = len(records)
    type_exact = 0
    group_exact = 0
    group_applicable = 0  # samples where GT has a group mapping

    # Per-category breakdown
    cat_stats: dict[str, dict] = defaultdict(lambda: {
        "total": 0, "type_exact": 0, "group_exact": 0, "group_applicable": 0,
    })

    for r in records:
        cat = r.get("category", "?")
        cat_stats[cat]["total"] += 1

        # defect_type_exact
        if r.get("metrics", {}).get("defect_type_exact", False):
            type_exact += 1
            cat_stats[cat]["type_exact"] += 1

        # defect_group_exact
        gt_dt = r.get("gt", {}).get("defect_type", "")
        pred_dt = ""
        pj = r.get("prediction_json")
        if pj and isinstance(pj, dict):
            pred_dt = pj.get("defect_type", "")

        gt_group = get_group(cat, gt_dt)
        if gt_group is not None:
            group_applicable += 1
            cat_stats[cat]["group_applicable"] += 1
            pred_group = get_group(cat, pred_dt)
            if pred_group == gt_group:
                group_exact += 1
                cat_stats[cat]["group_exact"] += 1

    return {
        "total": total,
        "type_exact": type_exact,
        "group_exact": group_exact,
        "group_applicable": group_applicable,
        "cat_stats": dict(cat_stats),
    }


def pct(n: int, d: int) -> str:
    return f"{n/d*100:.1f}%" if d > 0 else "N/A"


def main():
    variant_results: dict[str, dict] = {}
    for variant, path in JSONL_FILES.items():
        records = load_jsonl(path)
        variant_results[variant] = compute_rates(records)

    lines: list[str] = []
    w = lines.append

    w("# Defect Group Exact Analysis\n")
    w("## Alias Group Definitions\n")
    for cat, groups in sorted(ALIAS_GROUPS.items()):
        w(f"- **{cat}**:")
        for group_name, dtypes in groups.items():
            w(f"  - `{group_name}`: {', '.join(sorted(dtypes))}")
    w("")

    # ── Summary table: overall ──
    w("## Overall Comparison\n")
    w("| Variant | Total | type_exact | type_exact_% | group_exact | group_applicable | group_exact_% | Delta |")
    w("|---------|-------|-----------|-------------|-------------|-----------------|--------------|-------|")

    for variant in ["2B_base", "2B_lora", "4B_base", "4B_lora"]:
        s = variant_results[variant]
        type_pct = s["type_exact"] / s["total"] * 100 if s["total"] else 0
        if s["group_applicable"] > 0:
            group_pct = s["group_exact"] / s["group_applicable"] * 100
            delta = group_pct - type_pct
            delta_str = f"+{delta:.1f}%"
            group_pct_str = f"{group_pct:.1f}%"
        else:
            delta_str = "N/A"
            group_pct_str = "N/A"
        w(f"| {variant} | {s['total']} | {s['type_exact']}/{s['total']} | {type_pct:.1f}% | {s['group_exact']}/{s['group_applicable']} | {s['group_applicable']} | {group_pct_str} | {delta_str} |")

    w("")

    # ── Per-category tables ──
    # Collect all categories that have alias groups
    aliased_cats = sorted(ALIAS_GROUPS.keys())

    w("## Per-Category Breakdown\n")

    for cat in aliased_cats:
        w(f"### {cat}\n")

        # Check which groups apply
        groups = ALIAS_GROUPS[cat]
        group_names = sorted(groups.keys())
        w(f"Groups: {', '.join(f'`{g}` ({', '.join(sorted(groups[g]))})' for g in group_names)}\n")

        w("| Variant | Total | type_exact | type_% | group_exact | group_applicable | group_% | Delta |")
        w("|---------|-------|-----------|-------|-------------|-----------------|---------|-------|")

        for variant in ["2B_base", "2B_lora", "4B_base", "4B_lora"]:
            cs = variant_results[variant]["cat_stats"].get(cat)
            if not cs or cs["total"] == 0:
                continue
            type_pct = cs["type_exact"] / cs["total"] * 100
            if cs["group_applicable"] > 0:
                group_pct = cs["group_exact"] / cs["group_applicable"] * 100
                delta = group_pct - type_pct
                delta_str = f"+{delta:.1f}%"
                group_pct_str = f"{group_pct:.1f}%"
            else:
                delta_str = "N/A"
                group_pct_str = "N/A"
            w(f"| {variant} | {cs['total']} | {cs['type_exact']}/{cs['total']} | {type_pct:.1f}% | {cs['group_exact']}/{cs['group_applicable']} | {cs['group_applicable']} | {group_pct_str} | {delta_str} |")

        w("")

    # ── Non-aliased categories summary ──
    w("## Non-Aliased Categories\n")
    w("These categories have no alias groups defined; defect_type_exact == defect_group_exact.\n")

    all_cats = set()
    for v in variant_results.values():
        all_cats.update(v["cat_stats"].keys())
    non_aliased = sorted(all_cats - set(ALIAS_GROUPS.keys()))

    if non_aliased:
        w("| Variant | Category | type_exact | type_% |")
        w("|---------|----------|-----------|-------|")
        for cat in non_aliased:
            for variant in ["2B_base", "2B_lora", "4B_base", "4B_lora"]:
                cs = variant_results[variant]["cat_stats"].get(cat)
                if not cs or cs["total"] == 0:
                    continue
                type_pct = cs["type_exact"] / cs["total"] * 100
                w(f"| {variant} | {cat} | {cs['type_exact']}/{cs['total']} | {type_pct:.1f}% |")
        w("")

    OUTPUT_MD.write_text("\n".join(lines))
    print(f"Written: {OUTPUT_MD}")

    # Print summary
    for variant in ["2B_base", "2B_lora", "4B_base", "4B_lora"]:
        s = variant_results[variant]
        type_pct = s["type_exact"] / s["total"] * 100
        group_pct = s["group_exact"] / s["group_applicable"] * 100 if s["group_applicable"] else 0
        print(f"  {variant}: type_exact={type_pct:.1f}%, group_exact={group_pct:.1f}%, delta=+{group_pct-type_pct:.1f}%")


if __name__ == "__main__":
    main()
