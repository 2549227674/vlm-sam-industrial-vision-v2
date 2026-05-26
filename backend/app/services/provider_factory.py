# Phase 10.1: Provider factory — builds providers from env/config.
#
# No credentials read. No secrets logged. Provider-neutral.

from __future__ import annotations

import os

from backend.app.services.vlm_provider import (
    CloudVlmProvider,
    EdgeVlmProvider,
    ProviderConfigError,
    TemplateProvider,
    VlmProvider,
)


def get_provider(
    provider_name: str,
    *,
    edge_vlm_mode: str | None = None,
    edge_vlm_command: str | None = None,
    edge_vlm_endpoint: str | None = None,
    edge_vlm_model_name: str | None = None,
    timeout_s: int = 30,
) -> VlmProvider:
    """Build a provider by name. Raises ProviderConfigError for unknown names."""
    if provider_name == "template":
        return TemplateProvider()
    if provider_name == "edge_vlm":
        return EdgeVlmProvider(
            mode=edge_vlm_mode or "disabled",
            command=edge_vlm_command,
            endpoint=edge_vlm_endpoint,
            model_name=edge_vlm_model_name or "qwen3-vl-2b-base",
            timeout_s=timeout_s,
        )
    if provider_name == "cloud_vlm":
        return CloudVlmProvider()
    raise ProviderConfigError(
        f"Unknown enrichment provider: {provider_name!r}. "
        f"Must be 'template', 'edge_vlm', or 'cloud_vlm'."
    )


def get_provider_from_env() -> VlmProvider:
    """Build provider from environment variables.

    Environment variables:
        ENRICHMENT_PROVIDER: "edge_vlm" (default) | "template" | "cloud_vlm"
        EDGE_VLM_MODE: "disabled" (default) | "subprocess" | "http"
        EDGE_VLM_COMMAND: subprocess command (optional)
        EDGE_VLM_ENDPOINT: HTTP endpoint URL (optional)
        EDGE_VLM_MODEL_NAME: model identifier (default "qwen3-vl-2b-base")
        ENRICHMENT_TIMEOUT_S: per-call timeout in seconds (default 30)

    Does NOT read or require any CLOUD_VLM_* credentials.
    """
    provider_name = os.environ.get("ENRICHMENT_PROVIDER", "edge_vlm")
    timeout_s = int(os.environ.get("ENRICHMENT_TIMEOUT_S", "30"))

    return get_provider(
        provider_name,
        edge_vlm_mode=os.environ.get("EDGE_VLM_MODE", "disabled"),
        edge_vlm_command=os.environ.get("EDGE_VLM_COMMAND") or None,
        edge_vlm_endpoint=os.environ.get("EDGE_VLM_ENDPOINT") or None,
        edge_vlm_model_name=os.environ.get("EDGE_VLM_MODEL_NAME", "qwen3-vl-2b-base"),
        timeout_s=timeout_s,
    )
