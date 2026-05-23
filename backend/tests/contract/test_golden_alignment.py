"""Golden sample alignment test.

Validates that the simulator's fabricate_metadata() output matches the backend
Pydantic DefectCreate schema. Ensures cross-stack contract consistency without
requiring HTTP or network.
"""

import copy
import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.app.schemas.defect import DefectCreate
from simulator.line_runner import fabricate_metadata, generate_trace_events


# ── Simulator → Pydantic alignment ───────────────────────────────────────────


def _make_sim_meta(**overrides) -> dict:
    base = fabricate_metadata(
        category="metal_nut",
        line_id="L1",
        defect_type="scratch",
        variant="2B_base",
        edge_ts=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return base


def test_simulator_meta_validates_against_pydantic():
    """Simulator's fabricate_metadata() must produce a valid DefectCreate."""
    for category in ["metal_nut", "screw", "pill", "bottle", "tile"]:
        for variant in ["2B_base", "2B_lora"]:
            meta = fabricate_metadata(
                category=category,
                line_id="L1",
                defect_type="scratch",
                variant=variant,
                edge_ts=datetime.now(timezone.utc),
            )
            model = DefectCreate.model_validate(meta)
            assert model.category == category
            assert model.variant == variant


def test_simulator_trace_events_valid():
    meta = _make_sim_meta()
    model = DefectCreate.model_validate(meta)
    assert model.trace_events is not None
    assert len(model.trace_events) >= 5
    for event in model.trace_events:
        assert event.dur >= 0, f"Negative dur in trace event: {event.name}"
        assert event.ts >= 0, f"Negative ts in trace event: {event.name}"
        assert event.ph == "X"


def test_simulator_bbox_within_bounds():
    """All bboxes from simulator must satisfy x+w <= 1 and y+h <= 1."""
    for _ in range(20):
        meta = fabricate_metadata(
            category="metal_nut",
            line_id="L1",
            defect_type="scratch",
            variant="2B_base",
            edge_ts=datetime.now(timezone.utc),
        )
        model = DefectCreate.model_validate(meta)
        for bbox in model.bboxes:
            assert bbox.x + bbox.w <= 1.0 + 1e-9, f"x+w overflow: {bbox}"
            assert bbox.y + bbox.h <= 1.0 + 1e-9, f"y+h overflow: {bbox}"


def test_simulator_pipeline_ms_has_all_stages():
    meta = _make_sim_meta()
    model = DefectCreate.model_validate(meta)
    assert set(model.pipeline_ms.keys()) == {"efficientad", "fastsam", "qwen3vl"}


def test_simulator_edge_ts_is_aware():
    meta = _make_sim_meta()
    model = DefectCreate.model_validate(meta)
    assert model.edge_ts.tzinfo is not None


def test_simulator_vlm_metrics_valid():
    meta = _make_sim_meta()
    model = DefectCreate.model_validate(meta)
    assert model.vlm_metrics is not None
    assert model.vlm_metrics.ttft_ms >= 0
    assert model.vlm_metrics.decode_tps >= 0
    assert model.vlm_metrics.prompt_tokens >= 0
    assert model.vlm_metrics.output_tokens >= 0
    assert model.vlm_metrics.rss_mb >= 0


# ── JSON Schema validate fixtures ────────────────────────────────────────────

try:
    import jsonschema

    def _load_schema():
        schema_path = (
            __import__("pathlib").Path(__file__).resolve().parent.parent.parent.parent
            / "docs" / "schema" / "defect_report.v1.2.schema.json"
        )
        return json.loads(schema_path.read_text(encoding="utf-8"))

    def _load_fixture(name: str) -> dict:
        path = __import__("pathlib").Path(__file__).parent / "fixtures" / name
        return json.loads(path.read_text(encoding="utf-8"))

    def test_valid_minimal_against_json_schema():
        schema = _load_schema()
        data = _load_fixture("edge_report_valid_minimal_v1_2.json")
        jsonschema.validate(instance=data, schema=schema)

    def test_valid_full_against_json_schema():
        schema = _load_schema()
        data = _load_fixture("edge_report_valid_full_v1_2.json")
        jsonschema.validate(instance=data, schema=schema)

except ImportError:
    pytest.skip("jsonschema not installed — skipping JSON Schema validation tests", allow_module_level=True)
