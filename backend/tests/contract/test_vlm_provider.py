"""Phase 10.1: VLM provider interface + TemplateProvider + EdgeVlmProvider tests.

Tests for backend/app/services/vlm_provider.py — provider contract and behavior.
"""

import json

import pytest

from backend.app.services.enrichment_guard import validate_vlm_output
from backend.app.services.vlm_provider import (
    CloudVlmProvider,
    EdgeVlmProvider,
    ProviderConfigError,
    ProviderUnavailableError,
    TemplateProvider,
    VlmEnrichmentInput,
    VlmEnrichmentOutput,
    VlmProvider,
    VlmProviderError,
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
async def test_template_provider_raw_response_is_valid_json():
    """TemplateProvider raw_response is valid JSON."""
    provider = TemplateProvider()
    out = await provider.enrich(_make_input())
    data = json.loads(out.raw_response)
    assert "observation" in data
    assert "severity_reason" in data
    assert "accepted_box_ids" in data


@pytest.mark.asyncio
async def test_template_provider_raw_response_passes_guard():
    """TemplateProvider raw_response passes hallucination guard."""
    provider = TemplateProvider()
    inp = _make_input()
    out = await provider.enrich(inp)
    validated = validate_vlm_output(out.raw_response, input_box_ids=inp.box_ids)
    assert validated["observation"] == out.observation
    assert validated["severity_reason"] == out.severity_reason
    assert validated["accepted_box_ids"] == out.accepted_box_ids


@pytest.mark.asyncio
async def test_template_provider_output_passes_guard():
    """TemplateProvider output dict passes hallucination guard."""
    provider = TemplateProvider()
    inp = _make_input()
    out = await provider.enrich(inp)
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


@pytest.mark.asyncio
async def test_template_provider_deterministic():
    """TemplateProvider returns identical output for same input."""
    provider = TemplateProvider()
    inp = _make_input()
    out1 = await provider.enrich(inp)
    out2 = await provider.enrich(inp)
    assert out1.observation == out2.observation
    assert out1.severity_reason == out2.severity_reason
    assert out1.accepted_box_ids == out2.accepted_box_ids


# ── EdgeVlmProvider ──────────────────────────────────────────────────────────

def test_edge_vlm_provider_name():
    """EdgeVlmProvider has provider_name='edge_vlm'."""
    provider = EdgeVlmProvider()
    assert provider.provider_name == "edge_vlm"


def test_edge_vlm_provider_default_model():
    """EdgeVlmProvider default model is 'qwen3-vl-2b-base'."""
    provider = EdgeVlmProvider()
    assert provider.provider_model == "qwen3-vl-2b-base"


def test_edge_vlm_provider_custom_model():
    """EdgeVlmProvider accepts custom model_name."""
    provider = EdgeVlmProvider(model_name="qwen3-vl-4b-base")
    assert provider.provider_model == "qwen3-vl-4b-base"


@pytest.mark.asyncio
async def test_edge_vlm_disabled_raises_unavailable():
    """EdgeVlmProvider disabled mode raises ProviderUnavailableError."""
    provider = EdgeVlmProvider(mode="disabled")
    with pytest.raises(ProviderUnavailableError, match="disabled"):
        await provider.enrich(_make_input())


@pytest.mark.asyncio
async def test_edge_vlm_subprocess_without_command_raises_config():
    """EdgeVlmProvider subprocess mode without command raises ProviderConfigError."""
    with pytest.raises(ProviderConfigError, match="requires a command"):
        EdgeVlmProvider(mode="subprocess", command=None)


@pytest.mark.asyncio
async def test_edge_vlm_http_without_endpoint_raises_config():
    """EdgeVlmProvider http mode without endpoint raises ProviderConfigError."""
    with pytest.raises(ProviderConfigError, match="requires an endpoint"):
        EdgeVlmProvider(mode="http", endpoint=None)


def test_edge_vlm_unsupported_mode_raises_config():
    """EdgeVlmProvider with unsupported mode raises ProviderConfigError."""
    with pytest.raises(ProviderConfigError, match="Unsupported"):
        EdgeVlmProvider(mode="cuda")


@pytest.mark.asyncio
async def test_edge_vlm_subprocess_empty_stdout_raises():
    """EdgeVlmProvider subprocess with empty stdout raises VlmProviderError."""
    provider = EdgeVlmProvider(mode="subprocess", command="/usr/bin/echo")
    with pytest.raises(VlmProviderError, match="empty stdout"):
        await provider.enrich(_make_input())


@pytest.mark.asyncio
async def test_edge_vlm_http_raises_not_wired():
    """EdgeVlmProvider http mode raises ProviderUnavailableError (not yet wired)."""
    provider = EdgeVlmProvider(mode="http", endpoint="http://localhost:8001/vlm")
    with pytest.raises(ProviderUnavailableError, match="not yet wired"):
        await provider.enrich(_make_input())


# ── CloudVlmProvider (stub) ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cloud_vlm_provider_raises_unavailable():
    """CloudVlmProvider raises ProviderUnavailableError."""
    provider = CloudVlmProvider()
    with pytest.raises(ProviderUnavailableError, match="not implemented"):
        await provider.enrich(_make_input())


def test_cloud_vlm_provider_name():
    """CloudVlmProvider has provider_name='cloud_vlm'."""
    provider = CloudVlmProvider()
    assert provider.provider_name == "cloud_vlm"


def test_cloud_vlm_provider_default_model_empty():
    """CloudVlmProvider default model is empty (no vendor hardcoded)."""
    provider = CloudVlmProvider()
    assert provider.provider_model == ""


# ── VlmEnrichmentInput ──────────────────────────────────────────────────────

def test_input_box_ids_property():
    """VlmEnrichmentInput.box_ids returns [0, 1, ...] based on bboxes length."""
    inp = _make_input(bboxes=[{"x": 0, "y": 0, "w": 0.1, "h": 0.1}] * 3)
    assert inp.box_ids == [0, 1, 2]


def test_input_box_ids_empty():
    """VlmEnrichmentInput.box_ids is empty when bboxes is empty."""
    inp = _make_input(bboxes=[])
    assert inp.box_ids == []
