# Phase 10.1: VLM provider interface and implementations.
#
# Provider-neutral design — no hardcoded vendor, model, or endpoint.
# TemplateProvider is always available as fallback.

from __future__ import annotations

import asyncio
import json
import logging
import shlex
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


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
        if self._mode == "http":
            raise ProviderUnavailableError(
                "EdgeVlmProvider HTTP execution is not yet wired. "
                "Will be implemented in a later step."
            )
        if self._mode == "subprocess":
            return await self._run_subprocess(inp)
        # Unreachable due to __init__ validation, but defensive
        raise ProviderConfigError(f"Unknown mode: {self._mode!r}")

    async def _run_subprocess(self, inp: VlmEnrichmentInput) -> VlmEnrichmentOutput:
        """Execute VLM via subprocess (stdin/stdout JSON protocol)."""
        if not inp.image_path:
            raise ProviderConfigError(
                "EdgeVlmProvider subprocess requires a resolved image path."
            )

        argv = shlex.split(self._command)
        payload = self._build_payload(inp)
        payload_json = json.dumps(payload, ensure_ascii=False)

        logger.info(
            "EdgeVlmProvider subprocess: mode=%s, model=%s, timeout=%ds",
            self._mode, self.provider_model, self._timeout_s,
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(input=payload_json.encode("utf-8")),
                    timeout=self._timeout_s,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise ProviderTimeoutError(
                    f"EdgeVlmProvider subprocess timed out after {self._timeout_s}s."
                )

        except FileNotFoundError as exc:
            raise ProviderUnavailableError(
                f"EdgeVlmProvider subprocess command not found: {exc}"
            ) from exc
        except PermissionError as exc:
            raise ProviderUnavailableError(
                f"EdgeVlmProvider subprocess permission denied: {exc}"
            ) from exc

        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip()

        if proc.returncode != 0:
            truncated_stderr = stderr[:512] if stderr else "(no stderr)"
            raise VlmProviderError(
                f"EdgeVlmProvider subprocess exited with code {proc.returncode}. "
                f"stderr: {truncated_stderr}"
            )

        if not stdout:
            raise VlmProviderError(
                "EdgeVlmProvider subprocess returned empty stdout."
            )

        return VlmEnrichmentOutput(
            observation="",  # Guard will validate raw_response, not these
            severity_reason="",
            accepted_box_ids=[],
            raw_response=stdout,
            provider=self.provider_name,
            provider_model=self.provider_model,
        )

    @staticmethod
    def _build_payload(inp: VlmEnrichmentInput) -> dict:
        """Build the JSON payload for subprocess stdin."""
        boxes = [
            {"box_id": i, **bbox}
            for i, bbox in enumerate(inp.bboxes)
        ]
        return {
            "task": "phase10.1_vlm_enrichment",
            "prompt_version": inp.prompt_version,
            "image_path": inp.image_path,
            "category": inp.category,
            "defect_type": inp.defect_type,
            "confidence": inp.confidence,
            "bbox_format": "normalized_top_left_xywh",
            "boxes": boxes,
            "localization_source": inp.localization_source,
            "label_source": inp.label_source,
            "allowed_output_fields": ["observation", "severity_reason", "accepted_box_ids"],
            "forbidden_output_fields": [
                "bbox", "bboxes", "mask", "category", "defect_type",
                "confidence", "anomaly_score", "geometry_correction",
                "localization_source", "label_source",
            ],
            "language": "zh-CN",
            "style": "concise inspector note, no speculation",
        }


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
