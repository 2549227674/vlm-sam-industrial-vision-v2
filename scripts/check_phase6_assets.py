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
    print("  FastSAM-s (15-class calibrated RKNN INT8)")
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
    """Check RKLLM converted models in rkllm_15cls/."""
    print(f"\n{SEPARATOR}")
    print("  Qwen3-VL RKLLM Models (W8A8, rkllm_15cls/)")
    print(SEPARATOR)

    issues: list[str] = []
    rkllm_dir = MODELS_DIR / "qwen3vl_models" / "rkllm_15cls"

    # Required artifacts (Phase 6 Track B complete)
    required = [
        ("2B base RKLLM", "qwen3vl_2b_w8a8_base.rkllm"),
        ("2B LoRA 15cls RKLLM", "qwen3vl_2b_w8a8_lora_15cls.rkllm"),
        ("4B base RKLLM", "qwen3vl_4b_w8a8_base.rkllm"),
        ("4B LoRA 15cls RKLLM", "qwen3vl_4b_w8a8_lora_15cls.rkllm"),
        ("2B vision encoder", "qwen3vl_2b_vision.rknn"),
        ("4B vision encoder", "qwen3vl_4b_vision.rknn"),
    ]

    # Optional (none currently)
    optional: list[tuple[str, str]] = []

    if not rkllm_dir.exists():
        print("  [EMPTY]   rkllm_15cls/ directory does not exist")
        issues.append("rkllm_15cls: directory does not exist")
        return issues

    for label, filename in required:
        path = rkllm_dir / filename
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"  [OK]      {label:24s}  {filename}  ({size_mb:.1f} MB)")
            # Check for sha256 sidecar
            sha_path = path.with_suffix(path.suffix + ".sha256") if not filename.endswith(".sha256") else path
            # Try the common .sha256 naming
            sha_path = path.parent / (filename.replace(".rkllm", ".sha256").replace(".rknn", ".sha256"))
            if not sha_path.exists():
                print(f"            {'':24s}  (sha256 sidecar missing)")
        else:
            print(f"  [MISSING] {label:24s}  {filename}")
            issues.append(f"rkllm_15cls/{filename}: missing")

    print()
    for label, filename in optional:
        path = rkllm_dir / filename
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"  [OK]      {label:24s}  {filename}  ({size_mb:.1f} MB)")
        else:
            print(f"  [PENDING] {label:24s}  {filename}  (optional for Phase 8 comparison)")

    return issues


def check_qwen3vl_rkllm_v1() -> list[str]:
    """Check v1 3cls reference models (informational)."""
    print(f"\n{SEPARATOR}")
    print("  Qwen3-VL RKLLM v1 3cls (reference only)")
    print(SEPARATOR)

    rkllm_v1 = MODELS_DIR / "qwen3vl_models" / "rkllm_v1_3cls"
    expected_v1 = [
        "qwen3vl_2b_w8a8_lora.rkllm",
        "qwen3vl_vision.rknn",
    ]

    if not rkllm_v1.exists():
        print("    [INFO]    directory does not exist")
        return []

    for name in expected_v1:
        path = rkllm_v1 / name
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"    [OK]      {name}  ({size_mb:.1f} MB)")
        else:
            print(f"    [INFO]    {name}  (not present)")

    return []


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
    check_qwen3vl_rkllm_v1()  # informational only, never adds issues

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
