# Phase 10.1: VLM provider interface and implementations.
#
# Provider-neutral design — no hardcoded vendor, model, or endpoint.
# TemplateProvider is always available as fallback.

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


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


class VlmProvider(ABC):
    """Abstract base for enrichment providers."""

    provider_name: str = ""
    provider_model: str = ""

    @abstractmethod
    async def enrich(self, inp: VlmEnrichmentInput) -> VlmEnrichmentOutput:
        """Run enrichment and return validated output. Raises on error."""
        ...


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
        return VlmEnrichmentOutput(
            observation=observation,
            severity_reason=severity_reason,
            accepted_box_ids=inp.box_ids,
            raw_response="template",
            provider="template",
            provider_model="template",
        )


class EdgeVlmProvider(VlmProvider):
    """Edge VLM provider — primary Phase 10.1 provider.

    Supports subprocess / http / disabled modes via config.
    NOT implemented in Step 2a — raises NotImplementedError.
    """

    provider_name: str = "edge_vlm"
    provider_model: str = "qwen3-vl-2b-base"

    def __init__(self, mode: str = "disabled"):
        self._mode = mode

    async def enrich(self, inp: VlmEnrichmentInput) -> VlmEnrichmentOutput:
        raise NotImplementedError(
            "EdgeVlmProvider.enrich() is not yet implemented. "
            "Use TemplateProvider as fallback."
        )


class CloudVlmProvider(VlmProvider):
    """Cloud VLM provider — optional future comparison/fallback.

    NOT implemented. Provider-neutral — no vendor hardcoded.
    If requested, stop and ask user for provider choice and credentials.
    """

    provider_name: str = "cloud_vlm"
    provider_model: str = ""

    async def enrich(self, inp: VlmEnrichmentInput) -> VlmEnrichmentOutput:
        raise NotImplementedError(
            "CloudVlmProvider is not implemented. "
            "No vendor or credentials are configured."
        )
