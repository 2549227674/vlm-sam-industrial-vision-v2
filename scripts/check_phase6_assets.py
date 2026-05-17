#!/usr/bin/env python3
"""Phase 6 v2 asset readiness check.

Prints the status of all model artifacts required before running
RKNN / RKLLM conversions. No downloads, no conversions, no file moves.

Usage:
    python scripts/check_phase6_assets.py
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"

# MVTec AD full 15 classes
CATEGORIES = [
    "bottle", "cable", "capsule", "carpet", "grid",
    "hazelnut", "leather", "metal_nut", "pill", "screw",
    "tile", "toothbrush", "transistor", "wood", "zipper",
]

SEPARATOR = "=" * 60


def check_efficientad() -> list[str]:
    """Check EfficientAD-S: 15 model.rknn files."""
    print(f"\n{SEPARATOR}")
    print("  EfficientAD-S (15 classes -> RKNN INT8)")
    print(SEPARATOR)

    base = MODELS_DIR / "efficientad_models"
    existing: list[str] = []
    missing: list[str] = []

    for cat in CATEGORIES:
        rknn_path = base / cat / "model.rknn"
        if rknn_path.exists():
            existing.append(cat)
            print(f"  [OK]      {cat:14s}  {rknn_path.relative_to(PROJECT_ROOT)}")
        else:
            missing.append(cat)
            print(f"  [MISSING] {cat:14s}  {rknn_path.relative_to(PROJECT_ROOT)}")

    print(f"\n  RKNN existing: {len(existing)}/{len(CATEGORIES)}")
    if missing:
        print(f"  Missing:       {', '.join(missing)}")
    return [f"EfficientAD RKNN missing: {', '.join(missing)}"] if missing else []


def check_fastsam() -> list[str]:
    """Check FastSAM: fastsam_s.rknn + calib_dataset.txt."""
    print(f"\n{SEPARATOR}")
    print("  FastSAM-s (ONNX -> RKNN INT8)")
    print(SEPARATOR)

    issues: list[str] = []
    base = MODELS_DIR / "fastsam_models"

    rknn_path = base / "fastsam_s.rknn"
    onnx_path = base / "fastsam_s.onnx"
    calib_path = base / "calib_dataset.txt"

    for label, path in [
        ("ONNX (input)", onnx_path),
        ("RKNN (output)", rknn_path),
        ("Calib dataset", calib_path),
    ]:
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"  [OK]      {label:18s}  {path.name}  ({size_mb:.1f} MB)")
        else:
            print(f"  [MISSING] {label:18s}  {path.name}")
            if label != "ONNX (input)":
                issues.append(f"FastSAM: {path.name} missing")
            else:
                issues.append(f"FastSAM: {path.name} missing (run convert_fastsam_onnx.py first)")

    return issues


def check_qwen3vl_adapters() -> list[str]:
    """Check Qwen3-VL LoRA adapters (2B 15cls + 4B)."""
    print(f"\n{SEPARATOR}")
    print("  Qwen3-VL LoRA Adapters")
    print(SEPARATOR)

    issues: list[str] = []
    adapters = [
        ("2B (15cls)", MODELS_DIR / "qwen3vl_lora_adapter_15cls"),
        ("4B", MODELS_DIR / "qwen3vl_lora_4b_adapter"),
    ]

    for label, path in adapters:
        config = path / "adapter_config.json"
        weights = path / "adapter_model.safetensors"
        has_config = config.exists()
        has_weights = weights.exists()

        if has_config and has_weights:
            w_mb = weights.stat().st_size / (1024 * 1024)
            print(f"  [OK]      {label:14s}  adapter_model.safetensors ({w_mb:.1f} MB)")
        else:
            missing_parts = []
            if not has_config:
                missing_parts.append("adapter_config.json")
            if not has_weights:
                missing_parts.append("adapter_model.safetensors")
            print(f"  [MISSING] {label:14s}  missing: {', '.join(missing_parts)}")
            issues.append(f"Qwen3-VL {label} adapter: {', '.join(missing_parts)} missing")

    return issues


def check_qwen3vl_merged() -> list[str]:
    """Check merged LoRA directories."""
    print(f"\n{SEPARATOR}")
    print("  Qwen3-VL Merged LoRA (pre-RKLLM conversion)")
    print(SEPARATOR)

    issues: list[str] = []
    merged_dirs = [
        ("merged_lora_15cls (2B)", MODELS_DIR / "qwen3vl_models" / "merged_lora_15cls"),
        ("merged_lora_v1_3cls", MODELS_DIR / "qwen3vl_models" / "merged_lora_v1_3cls"),
    ]

    for label, path in merged_dirs:
        if not path.exists():
            print(f"  [EMPTY]   {label:28s}  directory does not exist")
            if "15cls" in label:
                issues.append(f"{label}: directory does not exist (run LLaMA-Factory export_model)")
        else:
            contents = list(path.iterdir())
            if contents:
                print(f"  [OK]      {label:28s}  {len(contents)} files")
            else:
                print(f"  [EMPTY]   {label:28s}  directory exists but is empty")
                if "15cls" in label:
                    issues.append(f"{label}: empty (run LLaMA-Factory export_model)")

    return issues


def check_qwen3vl_rkllm() -> list[str]:
    """Check RKLLM converted models."""
    print(f"\n{SEPARATOR}")
    print("  Qwen3-VL RKLLM Models (W8A8)")
    print(SEPARATOR)

    issues: list[str] = []

    # rkllm_15cls
    rkllm_15cls = MODELS_DIR / "qwen3vl_models" / "rkllm_15cls"
    print(f"\n  rkllm_15cls/")
    if not rkllm_15cls.exists():
        print("    [EMPTY]   directory does not exist")
        issues.append("rkllm_15cls: directory does not exist (run export_rkllm.py)")
    else:
        contents = list(rkllm_15cls.iterdir())
        if contents:
            for f in sorted(contents):
                size_mb = f.stat().st_size / (1024 * 1024)
                print(f"    [OK]      {f.name}  ({size_mb:.1f} MB)")
        else:
            print("    [EMPTY]   directory exists but is empty")
            issues.append("rkllm_15cls: empty (run export_rkllm.py)")

    # rkllm_v1_3cls
    rkllm_v1 = MODELS_DIR / "qwen3vl_models" / "rkllm_v1_3cls"
    expected_v1 = [
        "qwen3vl_2b_w8a8_base.rkllm",
        "qwen3vl_2b_w8a8_lora.rkllm",
        "qwen3vl_vision.rknn",
    ]

    print(f"\n  rkllm_v1_3cls/")
    if not rkllm_v1.exists():
        print("    [MISSING] directory does not exist")
        issues.append("rkllm_v1_3cls: directory does not exist")
    else:
        for name in expected_v1:
            path = rkllm_v1 / name
            if path.exists():
                size_mb = path.stat().st_size / (1024 * 1024)
                print(f"    [OK]      {name}  ({size_mb:.1f} MB)")
            else:
                print(f"    [MISSING] {name}")
                issues.append(f"rkllm_v1_3cls/{name}: missing")

    return issues


def main() -> None:
    print(SEPARATOR)
    print("  Phase 6 v2 Asset Readiness Check")
    print(f"  Project root: {PROJECT_ROOT}")
    print(SEPARATOR)

    all_issues: list[str] = []
    all_issues.extend(check_efficientad())
    all_issues.extend(check_fastsam())
    all_issues.extend(check_qwen3vl_adapters())
    all_issues.extend(check_qwen3vl_merged())
    all_issues.extend(check_qwen3vl_rkllm())

    print(f"\n{SEPARATOR}")
    print("  Summary")
    print(SEPARATOR)

    if all_issues:
        print(f"\n  {len(all_issues)} issue(s) found:\n")
        for i, issue in enumerate(all_issues, 1):
            print(f"    {i}. {issue}")
    else:
        print("\n  All assets ready. No issues found.")

    print()
    return len(all_issues)


if __name__ == "__main__":
    raise SystemExit(main())
