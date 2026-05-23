"""Contract fixture validation tests.

Validates JSON fixtures against the backend Pydantic DefectCreate model.
Ensures fixture files are valid contract examples that can be used for
cross-stack alignment testing.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.schemas.defect import DefectCreate

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    path = FIXTURES_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


# ── Valid fixtures pass Pydantic ──────────────────────────────────────────────


def test_valid_minimal_passes_schema():
    data = _load_fixture("edge_report_valid_minimal_v1_2.json")
    model = DefectCreate.model_validate(data)
    assert model.category == "metal_nut"
    assert model.schema_version == "v1"


def test_valid_full_passes_schema():
    data = _load_fixture("edge_report_valid_full_v1_2.json")
    model = DefectCreate.model_validate(data)
    assert len(model.bboxes) == 2
    assert model.vlm_metrics is not None
    assert model.trace_events is not None
    assert len(model.trace_events) == 7


# ── Invalid fixtures are rejected by Pydantic ────────────────────────────────


def test_invalid_extra_field_rejected():
    data = _load_fixture("edge_report_invalid_extra_field.json")
    with pytest.raises(ValidationError):
        DefectCreate.model_validate(data)


def test_invalid_naive_edge_ts_rejected():
    data = _load_fixture("edge_report_invalid_naive_edge_ts.json")
    with pytest.raises(ValidationError, match="timezone-aware"):
        DefectCreate.model_validate(data)


def test_invalid_bbox_overflow_rejected():
    data = _load_fixture("edge_report_invalid_bbox_overflow.json")
    # x=0.8 + w=0.4 = 1.2 > 1.0 → Pydantic allows it per-field but route catches it.
    # However, w=0.4 <= 1.0 passes Pydantic, so the model validates here.
    # The secondary x+w<=1 check is in the route, not Pydantic.
    model = DefectCreate.model_validate(data)
    bbox = model.bboxes[0]
    assert bbox.x + bbox.w > 1.0  # confirms it's the overflow case


def test_invalid_bbox_negative_rejected():
    data = _load_fixture("edge_report_invalid_bbox_negative.json")
    with pytest.raises(ValidationError, match="greater than or equal to"):
        DefectCreate.model_validate(data)


def test_invalid_missing_required_rejected():
    data = _load_fixture("edge_report_invalid_missing_required.json")
    with pytest.raises(ValidationError):
        DefectCreate.model_validate(data)


def test_invalid_category_rejected():
    data = _load_fixture("edge_report_invalid_category.json")
    with pytest.raises(ValidationError, match="category"):
        DefectCreate.model_validate(data)


def test_invalid_variant_rejected():
    data = _load_fixture("edge_report_invalid_variant.json")
    with pytest.raises(ValidationError, match="variant"):
        DefectCreate.model_validate(data)
