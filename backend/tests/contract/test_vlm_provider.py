"""Phase 10.1: VLM provider interface + TemplateProvider tests.

Tests for backend/app/services/vlm_provider.py — provider contract and TemplateProvider behavior.
"""

import pytest

from backend.app.services.enrichment_guard import validate_vlm_output
from backend.app.services.vlm_provider import (
    CloudVlmProvider,
    EdgeVlmProvider,
    TemplateProvider,
    VlmEnrichmentInput,
    VlmEnrichmentOutput,
    VlmProvider,
)


def _make_input(**overrides) -> VlmEnrichmentInput:
    defaults = dict(
        image_path="/tmp/test.jpg",
        category="metal_nut",
        defect_type="scratch",
        confidence=0.95,
        bboxes=[{"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}],
        localization_source="ort_yolov8n_cpu",
        label_source="yolo_class_head",
    )
    defaults.update(overrides)
    return VlmEnrichmentInput(**defaults)


# ── VlmProvider is abstract ──────────────────────────────────────────────────

def test_vlm_provider_is_abstract():
    """VlmProvider cannot be instantiated directly."""
    with pytest.raises(TypeError):
        VlmProvider()  # type: ignore[abstract]


# ── TemplateProvider ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_template_provider_returns_template_name():
    """TemplateProvider returns provider='template'."""
    provider = TemplateProvider()
    out = await provider.enrich(_make_input())
    assert out.provider == "template"
    assert out.provider_model == "template"


@pytest.mark.asyncio
async def test_template_provider_returns_non_empty_strings():
    """TemplateProvider returns non-empty observation and severity_reason."""
    provider = TemplateProvider()
    out = await provider.enrich(_make_input())
    assert len(out.observation) > 0
    assert len(out.severity_reason) > 0


@pytest.mark.asyncio
async def test_template_provider_includes_all_box_ids():
    """TemplateProvider accepted_box_ids includes all input box IDs."""
    inp = _make_input(bboxes=[
        {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2},
        {"x": 0.5, "y": 0.5, "w": 0.1, "h": 0.1},
    ])
    provider = TemplateProvider()
    out = await provider.enrich(inp)
    assert out.accepted_box_ids == [0, 1]


@pytest.mark.asyncio
async def test_template_provider_empty_bboxes():
    """TemplateProvider handles empty bboxes gracefully."""
    inp = _make_input(bboxes=[])
    provider = TemplateProvider()
    out = await provider.enrich(inp)
    assert out.accepted_box_ids == []


@pytest.mark.asyncio
async def test_template_provider_observation_contains_category():
    """TemplateProvider observation references the category."""
    provider = TemplateProvider()
    out = await provider.enrich(_make_input(category="cable"))
    assert "cable" in out.observation


@pytest.mark.asyncio
async def test_template_provider_raw_response_is_template():
    """TemplateProvider raw_response is 'template' (not JSON from VLM)."""
    provider = TemplateProvider()
    out = await provider.enrich(_make_input())
    assert out.raw_response == "template"


@pytest.mark.asyncio
async def test_template_provider_output_passes_guard():
    """TemplateProvider output passes hallucination guard."""
    provider = TemplateProvider()
    inp = _make_input()
    out = await provider.enrich(inp)
    # Guard accepts dict with observation, severity_reason, accepted_box_ids
    validated = validate_vlm_output(
        {"observation": out.observation, "severity_reason": out.severity_reason, "accepted_box_ids": out.accepted_box_ids},
        input_box_ids=inp.box_ids,
    )
    assert validated["observation"]
    assert validated["severity_reason"]
    assert validated["accepted_box_ids"] == inp.box_ids


@pytest.mark.asyncio
async def test_template_provider_no_forbidden_keys_in_output():
    """TemplateProvider output contains no forbidden keys."""
    from backend.app.services.enrichment_guard import FORBIDDEN_KEYS
    provider = TemplateProvider()
    out = await provider.enrich(_make_input())
    output_dict = {
        "observation": out.observation,
        "severity_reason": out.severity_reason,
        "accepted_box_ids": out.accepted_box_ids,
    }
    for key in FORBIDDEN_KEYS:
        assert key not in output_dict, f"forbidden key '{key}' found in TemplateProvider output"


# ── EdgeVlmProvider (stub) ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_edge_vlm_provider_not_implemented():
    """EdgeVlmProvider raises NotImplementedError."""
    provider = EdgeVlmProvider(mode="disabled")
    with pytest.raises(NotImplementedError, match="not yet implemented"):
        await provider.enrich(_make_input())


def test_edge_vlm_provider_name():
    """EdgeVlmProvider has provider_name='edge_vlm'."""
    provider = EdgeVlmProvider()
    assert provider.provider_name == "edge_vlm"


# ── CloudVlmProvider (stub) ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cloud_vlm_provider_not_implemented():
    """CloudVlmProvider raises NotImplementedError."""
    provider = CloudVlmProvider()
    with pytest.raises(NotImplementedError, match="not implemented"):
        await provider.enrich(_make_input())


def test_cloud_vlm_provider_name():
    """CloudVlmProvider has provider_name='cloud_vlm'."""
    provider = CloudVlmProvider()
    assert provider.provider_name == "cloud_vlm"


# ── VlmEnrichmentInput ──────────────────────────────────────────────────────

def test_input_box_ids_property():
    """VlmEnrichmentInput.box_ids returns [0, 1, ...] based on bboxes length."""
    inp = _make_input(bboxes=[{"x": 0, "y": 0, "w": 0.1, "h": 0.1}] * 3)
    assert inp.box_ids == [0, 1, 2]


def test_input_box_ids_empty():
    """VlmEnrichmentInput.box_ids is empty when bboxes is empty."""
    inp = _make_input(bboxes=[])
    assert inp.box_ids == []
