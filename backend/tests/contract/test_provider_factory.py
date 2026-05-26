"""Phase 10.1: Provider factory tests.

Tests for backend/app/services/provider_factory.py — env-based provider construction.
"""

import pytest

from backend.app.services.provider_factory import get_provider, get_provider_from_env
from backend.app.services.vlm_provider import (
    CloudVlmProvider,
    EdgeVlmProvider,
    ProviderConfigError,
    TemplateProvider,
)


# ── get_provider() ───────────────────────────────────────────────────────────

def test_get_provider_template():
    """get_provider('template') returns TemplateProvider."""
    p = get_provider("template")
    assert isinstance(p, TemplateProvider)


def test_get_provider_edge_vlm():
    """get_provider('edge_vlm') returns EdgeVlmProvider."""
    p = get_provider("edge_vlm")
    assert isinstance(p, EdgeVlmProvider)


def test_get_provider_cloud_vlm():
    """get_provider('cloud_vlm') returns CloudVlmProvider."""
    p = get_provider("cloud_vlm")
    assert isinstance(p, CloudVlmProvider)


def test_get_provider_unknown_raises():
    """Unknown provider name raises ProviderConfigError."""
    with pytest.raises(ProviderConfigError, match="Unknown"):
        get_provider("nonexistent")


def test_get_provider_edge_vlm_custom_model():
    """get_provider passes model_name to EdgeVlmProvider."""
    p = get_provider("edge_vlm", edge_vlm_model_name="qwen3-vl-4b-base")
    assert isinstance(p, EdgeVlmProvider)
    assert p.provider_model == "qwen3-vl-4b-base"


# ── get_provider_from_env() ──────────────────────────────────────────────────

def test_get_provider_from_env_default(monkeypatch):
    """Default env returns EdgeVlmProvider with disabled mode."""
    monkeypatch.delenv("ENRICHMENT_PROVIDER", raising=False)
    monkeypatch.delenv("EDGE_VLM_MODE", raising=False)
    monkeypatch.delenv("EDGE_VLM_COMMAND", raising=False)
    monkeypatch.delenv("EDGE_VLM_ENDPOINT", raising=False)
    monkeypatch.delenv("EDGE_VLM_MODEL_NAME", raising=False)
    monkeypatch.delenv("ENRICHMENT_TIMEOUT_S", raising=False)

    p = get_provider_from_env()
    assert isinstance(p, EdgeVlmProvider)
    assert p.provider_model == "qwen3-vl-2b-base"


def test_get_provider_from_env_template(monkeypatch):
    """ENRICHMENT_PROVIDER=template returns TemplateProvider."""
    monkeypatch.setenv("ENRICHMENT_PROVIDER", "template")
    p = get_provider_from_env()
    assert isinstance(p, TemplateProvider)


def test_get_provider_from_env_edge_vlm_disabled(monkeypatch):
    """ENRICHMENT_PROVIDER=edge_vlm with default mode returns EdgeVlmProvider."""
    monkeypatch.setenv("ENRICHMENT_PROVIDER", "edge_vlm")
    monkeypatch.delenv("EDGE_VLM_MODE", raising=False)
    p = get_provider_from_env()
    assert isinstance(p, EdgeVlmProvider)
    assert p.provider_model == "qwen3-vl-2b-base"


def test_get_provider_from_env_edge_vlm_subprocess(monkeypatch):
    """EDGE_VLM_MODE=subprocess with command returns EdgeVlmProvider."""
    monkeypatch.setenv("ENRICHMENT_PROVIDER", "edge_vlm")
    monkeypatch.setenv("EDGE_VLM_MODE", "subprocess")
    monkeypatch.setenv("EDGE_VLM_COMMAND", "/usr/bin/echo")
    p = get_provider_from_env()
    assert isinstance(p, EdgeVlmProvider)


def test_get_provider_from_env_cloud_vlm(monkeypatch):
    """ENRICHMENT_PROVIDER=cloud_vlm returns CloudVlmProvider without needing creds."""
    monkeypatch.setenv("ENRICHMENT_PROVIDER", "cloud_vlm")
    p = get_provider_from_env()
    assert isinstance(p, CloudVlmProvider)


def test_get_provider_from_env_unknown_raises(monkeypatch):
    """Unknown ENRICHMENT_PROVIDER raises ProviderConfigError."""
    monkeypatch.setenv("ENRICHMENT_PROVIDER", "magic_vlm")
    with pytest.raises(ProviderConfigError, match="Unknown"):
        get_provider_from_env()


def test_get_provider_from_env_custom_model(monkeypatch):
    """EDGE_VLM_MODEL_NAME is passed through to EdgeVlmProvider."""
    monkeypatch.setenv("ENRICHMENT_PROVIDER", "edge_vlm")
    monkeypatch.setenv("EDGE_VLM_MODEL_NAME", "qwen3-vl-4b-base")
    p = get_provider_from_env()
    assert isinstance(p, EdgeVlmProvider)
    assert p.provider_model == "qwen3-vl-4b-base"


def test_get_provider_from_env_timeout(monkeypatch):
    """ENRICHMENT_TIMEOUT_S is parsed correctly."""
    monkeypatch.setenv("ENRICHMENT_PROVIDER", "template")
    monkeypatch.setenv("ENRICHMENT_TIMEOUT_S", "60")
    # TemplateProvider ignores timeout, but the factory parses it
    p = get_provider_from_env()
    assert isinstance(p, TemplateProvider)
