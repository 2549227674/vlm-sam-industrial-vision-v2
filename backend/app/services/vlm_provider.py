# Phase 10.1: VLM provider interface and implementations.
#
# Provider-neutral design — no hardcoded vendor, model, or endpoint.
# TemplateProvider is always available as fallback.

from __future__ import annotations

import json
import shlex
from abc import ABC, abstractmethod
from dataclasses import dataclass


# ── Provider exceptions ──────────────────────────────────────────────────────

class VlmProviderError(Exception):
    """Base exception for VLM provider errors."""
    pass


class ProviderUnavailableError(VlmProviderError):
    """Provider is not available (disabled, not configured, or offline)."""
    pass


class ProviderConfigError(VlmProviderError):
    """Provider configuration is invalid or incomplete."""
    pass


class ProviderTimeoutError(VlmProviderError):
    """Provider call exceeded timeout. Future use."""
    pass


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class VlmEnrichmentInput:
    """Input payload for VLM enrichment. Immutable YOLO/ORT facts."""

    image_path: str | None
    category: str
    defect_type: str
    confidence: float
    bboxes: list[dict]
    localization_source: str | None = None
    label_source: str | None = None
    prompt_version: str = "phase10_1_obs_v1"

    @property
    def box_ids(self) -> list[int]:
        return list(range(len(self.bboxes)))


@dataclass
class VlmEnrichmentOutput:
    """Validated output from a VLM provider."""

    observation: str
    severity_reason: str
    accepted_box_ids: list[int]
    raw_response: str
    provider: str
    provider_model: str


# ── Abstract base ────────────────────────────────────────────────────────────

class VlmProvider(ABC):
    """Abstract base for enrichment providers."""

    provider_name: str = ""
    provider_model: str = ""

    @abstractmethod
    async def enrich(self, inp: VlmEnrichmentInput) -> VlmEnrichmentOutput:
        """Run enrichment and return validated output. Raises on error."""
        ...


# ── TemplateProvider ─────────────────────────────────────────────────────────

class TemplateProvider(VlmProvider):
    """Deterministic template fallback — always available, no external calls."""

    provider_name: str = "template"
    provider_model: str = "template"

    async def enrich(self, inp: VlmEnrichmentInput) -> VlmEnrichmentOutput:
        category = inp.category
        defect_type = inp.defect_type.replace("_", " ")
        observation = (
            f"[Template] {category}: {defect_type} detected "
            f"(confidence={inp.confidence:.2f}). "
            f"Automated template observation — no VLM enrichment applied."
        )
        severity_reason = (
            "[Template] Severity assigned by default rule. "
            "No VLM-based severity analysis available."
        )
        accepted_box_ids = inp.box_ids
        raw_response = json.dumps(
            {
                "observation": observation,
                "severity_reason": severity_reason,
                "accepted_box_ids": accepted_box_ids,
            },
            ensure_ascii=False,
        )
        return VlmEnrichmentOutput(
            observation=observation,
            severity_reason=severity_reason,
            accepted_box_ids=accepted_box_ids,
            raw_response=raw_response,
            provider="template",
            provider_model="template",
        )


# ── EdgeVlmProvider ──────────────────────────────────────────────────────────

class EdgeVlmProvider(VlmProvider):
    """Edge VLM provider — primary Phase 10.1 provider.

    Supports subprocess / http / disabled modes.
    Subprocess and HTTP execution will be wired in later steps.
    """

    provider_name: str = "edge_vlm"

    def __init__(
        self,
        mode: str = "disabled",
        command: str | None = None,
        endpoint: str | None = None,
        model_name: str = "qwen3-vl-2b-base",
        timeout_s: int = 30,
    ):
        self._mode = mode
        self._command = command
        self._endpoint = endpoint
        self.provider_model = model_name
        self._timeout_s = timeout_s

        if mode not in ("disabled", "subprocess", "http"):
            raise ProviderConfigError(
                f"Unsupported EdgeVlmProvider mode: {mode!r}. "
                f"Must be 'disabled', 'subprocess', or 'http'."
            )
        if mode == "subprocess" and not command:
            raise ProviderConfigError(
                "EdgeVlmProvider mode='subprocess' requires a command string."
            )
        if mode == "http" and not endpoint:
            raise ProviderConfigError(
                "EdgeVlmProvider mode='http' requires an endpoint URL."
            )

    async def enrich(self, inp: VlmEnrichmentInput) -> VlmEnrichmentOutput:
        if self._mode == "disabled":
            raise ProviderUnavailableError(
                "EdgeVlmProvider is disabled. Set EDGE_VLM_MODE=subprocess or http to enable."
            )
        if self._mode == "subprocess":
            raise ProviderUnavailableError(
                "EdgeVlmProvider subprocess execution is not yet wired. "
                "Will be implemented in a later step."
            )
        if self._mode == "http":
            raise ProviderUnavailableError(
                "EdgeVlmProvider HTTP execution is not yet wired. "
                "Will be implemented in a later step."
            )
        # Unreachable due to __init__ validation, but defensive
        raise ProviderConfigError(f"Unknown mode: {self._mode!r}")


# ── CloudVlmProvider ─────────────────────────────────────────────────────────

class CloudVlmProvider(VlmProvider):
    """Cloud VLM provider — optional future comparison/fallback.

    NOT implemented. Provider-neutral — no vendor hardcoded.
    If requested, stop and ask user for provider choice and credentials.
    """

    provider_name: str = "cloud_vlm"
    provider_model: str = ""

    def __init__(self, model_name: str = ""):
        self.provider_model = model_name

    async def enrich(self, inp: VlmEnrichmentInput) -> VlmEnrichmentOutput:
        raise ProviderUnavailableError(
            "CloudVlmProvider is not implemented. "
            "No vendor or credentials are configured. "
            "To use cloud VLM, provide provider choice and credentials."
        )
