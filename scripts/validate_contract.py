#!/usr/bin/env python3
"""Validate a JSON file against the DefectCreate contract schema.

Usage:
    python scripts/validate_contract.py <json_file>

Exit codes:
    0  — valid
    1  — invalid or file not found
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.schemas.defect import DefectCreate

try:
    import jsonschema

    SCHEMA_PATH = Path(__file__).resolve().parent.parent / "docs" / "schema" / "defect_report.v1.2.schema.json"
except ImportError:
    jsonschema = None


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/validate_contract.py <json_file>")
        return 1

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"ERROR: File not found: {path}")
        return 1

    data = json.loads(path.read_text(encoding="utf-8"))

    # Pydantic validation (always available)
    try:
        model = DefectCreate.model_validate(data)
        print(f"OK (Pydantic): {path.name} is a valid DefectCreate")
        print(f"  category={model.category}, severity={model.severity}, variant={model.variant}")
    except Exception as e:
        print(f"FAIL (Pydantic): {path.name} — {e}")
        return 1

    # JSON Schema validation (if jsonschema available)
    if jsonschema and SCHEMA_PATH.exists():
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(instance=data, schema=schema)
            print(f"OK (JSON Schema): matches {SCHEMA_PATH.name}")
        except jsonschema.ValidationError as e:
            print(f"FAIL (JSON Schema): {e.message}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
