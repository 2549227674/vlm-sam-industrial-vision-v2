#!/usr/bin/env python3
"""Export DefectCreate JSON Schema from backend Pydantic v2 model.

Usage:
    python scripts/export_contract_schema.py

Outputs:
    docs/schema/defect_report.v1.2.schema.json
"""

import json
import sys
from pathlib import Path

# Ensure backend package is importable from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.schemas.defect import BBox, DefectCreate, DefectRead, VlmMetrics, TraceEvent

SCHEMA_VERSION = "v1.2"
SCHEMA_VER_NUM = "1.2"  # without "v" prefix for file names
OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "schema"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    schemas = {
        "DefectCreate": DefectCreate.model_json_schema(),
        "DefectRead": DefectRead.model_json_schema(),
        "BBox": BBox.model_json_schema(),
        "VlmMetrics": VlmMetrics.model_json_schema(),
        "TraceEvent": TraceEvent.model_json_schema(),
    }

    # Write individual schemas
    for name, schema in schemas.items():
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = f"https://vision.example.com/schema/{name.lower()}.v{SCHEMA_VER_NUM}.schema.json"
        out = OUT_DIR / f"{name.lower()}.v{SCHEMA_VER_NUM}.schema.json"
        out.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  exported {out.relative_to(OUT_DIR.parent.parent)}")

    # Write combined bundle for contract validation
    bundle = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://vision.example.com/schema/defect_report.v{SCHEMA_VER_NUM}.schema.json",
        "title": f"Industrial Vision Defect Report Contract v{SCHEMA_VER_NUM}",
        "description": "Auto-generated from backend/app/schemas/defect.py — do not edit manually.",
        "$defs": schemas["DefectCreate"].get("$defs", {}),
        "properties": schemas["DefectCreate"].get("properties", {}),
        "required": schemas["DefectCreate"].get("required", []),
        "type": "object",
        "additionalProperties": False,
    }
    bundle_path = OUT_DIR / f"defect_report.v{SCHEMA_VER_NUM}.schema.json"
    bundle_path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  exported {bundle_path.relative_to(OUT_DIR.parent.parent)} (combined)")


if __name__ == "__main__":
    main()
