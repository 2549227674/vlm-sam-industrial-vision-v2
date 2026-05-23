#!/usr/bin/env python3
"""Check for contract schema drift.

Re-exports the JSON Schema from the backend Pydantic model and compares
it against the committed snapshot in docs/schema/. If they differ, the
script exits non-zero — meaning someone changed the schema without
bumping the contract version and updating the snapshot.

Usage:
    python scripts/check_contract_drift.py

Exit codes:
    0  — schema matches snapshot
    1  — drift detected (must re-export and update docs/API_CONTRACT.md)
"""

import json
import sys
from pathlib import Path

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.schemas.defect import DefectCreate

SCHEMA_VERSION = "1.2"
SCHEMA_DIR = Path(__file__).resolve().parent.parent / "docs" / "schema"
SNAPSHOT_PATH = SCHEMA_DIR / f"defect_report.v{SCHEMA_VERSION}.schema.json"


def main() -> int:
    if not SNAPSHOT_PATH.exists():
        print(f"ERROR: Snapshot not found: {SNAPSHOT_PATH}")
        print("  Run: python scripts/export_contract_schema.py")
        return 1

    # Re-export current schema
    current = DefectCreate.model_json_schema()
    current["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    current["$id"] = f"https://vision.example.com/schema/defect_report.v{SCHEMA_VERSION}.schema.json"
    current["title"] = f"Industrial Vision Defect Report Contract v{SCHEMA_VERSION}"
    current["description"] = "Auto-generated from backend/app/schemas/defect.py — do not edit manually."
    current["$defs"] = current.get("$defs", {})
    current["properties"] = current.get("properties", {})
    current["required"] = current.get("required", [])
    current["type"] = "object"
    current["additionalProperties"] = False

    # Load committed snapshot
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

    # Compare (order-insensitive via json.dumps sort_keys)
    current_str = json.dumps(current, indent=2, sort_keys=True, ensure_ascii=False)
    snapshot_str = json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False)

    if current_str == snapshot_str:
        print(f"OK: Schema matches snapshot ({SNAPSHOT_PATH.name})")
        return 0

    # Show diff summary
    print(f"DRIFT DETECTED: backend/app/schemas/defect.py differs from {SNAPSHOT_PATH.name}")
    print()
    print("Action required:")
    print("  1. If intentional change: bump contract version in docs/API_CONTRACT.md")
    print("     then run: python scripts/export_contract_schema.py")
    print("  2. If unintentional: revert the schema change")
    print()

    # Show which keys differ
    current_keys = set(current.get("properties", {}).keys())
    snapshot_keys = set(snapshot.get("properties", {}).keys())
    added = current_keys - snapshot_keys
    removed = snapshot_keys - current_keys
    if added:
        print(f"  Added properties: {sorted(added)}")
    if removed:
        print(f"  Removed properties: {sorted(removed)}")

    current_defs = set(current.get("$defs", {}).keys())
    snapshot_defs = set(snapshot.get("$defs", {}).keys())
    added_defs = current_defs - snapshot_defs
    removed_defs = snapshot_defs - current_defs
    if added_defs:
        print(f"  Added $defs: {sorted(added_defs)}")
    if removed_defs:
        print(f"  Removed $defs: {sorted(removed_defs)}")

    return 1


if __name__ == "__main__":
    sys.exit(main())
