# Phase 10.1: Enrichment API routes — manual trigger + status query + process.

import os

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import get_db
from backend.app.models.defect import Defect
from backend.app.models.enrichment import DefectEnrichment
from backend.app.schemas.enrichment import (
    DefectEnrichmentRead,
    EnrichmentCreatedResponse,
)
from backend.app.services.enrichment_worker import (
    process_enrichment_job,
    process_next_pending_enrichment,
)
from backend.app.services.enrichment_ws_events import build_enrichment_event
from backend.app.services.provider_factory import get_provider, get_provider_from_env
from backend.app.services.vlm_provider import (
    ProviderConfigError,
    TemplateProvider,
    VlmProvider,
)

router = APIRouter(prefix="/api", tags=["enrichment"])

_DEFAULT_PROVIDER = os.environ.get("ENRICHMENT_PROVIDER", "edge_vlm")
_DEFAULT_PROMPT_VERSION = os.environ.get("ENRICHMENT_PROMPT_VERSION", "phase10_1_obs_v1")

_PROVIDER_QUERY_VALUES = ("template", "edge_vlm", "cloud_vlm")


def _resolve_provider(provider_name: str | None) -> VlmProvider:
    """Resolve a provider query parameter to a VlmProvider instance.

    Args:
        provider_name: Query param value. None means use env default.

    Returns:
        VlmProvider instance.

    Raises:
        ValueError: For unknown or forbidden provider names.
    """
    if provider_name is None or provider_name == "":
        return get_provider_from_env()

    name = provider_name.strip().lower()

    if name == "template":
        return TemplateProvider()

    if name == "edge_vlm":
        return get_provider("edge_vlm",
            edge_vlm_mode=os.environ.get("EDGE_VLM_MODE", "disabled"),
            edge_vlm_command=os.environ.get("EDGE_VLM_COMMAND") or None,
            edge_vlm_endpoint=os.environ.get("EDGE_VLM_ENDPOINT") or None,
            edge_vlm_model_name=os.environ.get("EDGE_VLM_MODEL_NAME", "qwen3-vl-2b-base"),
            timeout_s=int(os.environ.get("ENRICHMENT_TIMEOUT_S", "30")),
        )

    if name == "cloud_vlm":
        raise ValueError("cloud_vlm is not implemented in Phase 10.1a")

    raise ValueError(f"Unknown provider: {provider_name!r}")


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


@router.post(
    "/defects/{defect_id}/enrich",
    response_model=EnrichmentCreatedResponse,
    status_code=202,
)
async def trigger_enrichment(
    defect_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Manual enrichment trigger — creates a pending job. Does not call VLM."""
    # 404: defect must exist
    defect = await db.get(Defect, defect_id)
    if not defect:
        return _error(404, "NOT_FOUND", f"Defect {defect_id} not found")

    # 400: bboxes must be non-empty
    if not defect.bboxes:
        return _error(400, "EMPTY_BBOXES", "Defect has no bboxes — cannot enrich")

    # 400: confidence must be > 0 (reject fallback placeholder)
    if defect.confidence <= 0:
        return _error(
            400, "ZERO_CONFIDENCE",
            "Defect has zero confidence (fallback placeholder) — cannot enrich",
        )

    # 400: reject known fallback placeholder pattern
    if (
        defect.defect_type == "anomaly"
        and defect.confidence == 0
        and len(defect.bboxes) == 1
        and abs(defect.bboxes[0].get("x", 0) - 0.3) < 0.01
        and abs(defect.bboxes[0].get("y", 0) - 0.3) < 0.01
        and abs(defect.bboxes[0].get("w", 0) - 0.4) < 0.01
        and abs(defect.bboxes[0].get("h", 0) - 0.4) < 0.01
    ):
        return _error(
            400, "FALLBACK_PLACEHOLDER",
            "Defect is a fallback placeholder — cannot enrich",
        )

    # 409: no duplicate pending/running job for same defect + provider + prompt
    existing_q = select(DefectEnrichment).where(
        DefectEnrichment.defect_id == defect_id,
        DefectEnrichment.provider == _DEFAULT_PROVIDER,
        DefectEnrichment.prompt_version == _DEFAULT_PROMPT_VERSION,
        DefectEnrichment.status.in_(("pending", "running")),
    )
    existing = (await db.execute(existing_q)).scalar_one_or_none()
    if existing:
        return _error(
            409, "DUPLICATE_ENRICHMENT",
            f"Active enrichment already exists (id={existing.id}, status={existing.status})",
        )

    # Create pending enrichment job
    enrichment = DefectEnrichment(
        defect_id=defect_id,
        provider=_DEFAULT_PROVIDER,
        provider_model="",
        prompt_version=_DEFAULT_PROMPT_VERSION,
        status="pending",
    )
    db.add(enrichment)
    await db.flush()
    await db.refresh(enrichment)

    # Emit WS event for manually triggered pending enrichment
    ws_manager = getattr(request.app.state, "ws_manager", None)
    if ws_manager:
        try:
            event = build_enrichment_event(
                defect_id=defect_id,
                enrichment_id=enrichment.id,
                status="pending",
                provider=_DEFAULT_PROVIDER,
            )
            await ws_manager.broadcast("dashboard", event)
        except Exception:
            pass  # best-effort

    return EnrichmentCreatedResponse(
        enrichment_id=enrichment.id,
        defect_id=defect_id,
        status="pending",
    )


@router.get("/defects/{defect_id}/enrichment", response_model=DefectEnrichmentRead)
async def get_enrichment(
    defect_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get the latest enrichment record for a defect."""
    q = (
        select(DefectEnrichment)
        .where(DefectEnrichment.defect_id == defect_id)
        .order_by(DefectEnrichment.created_at.desc())
        .limit(1)
    )
    result = (await db.execute(q)).scalar_one_or_none()
    if not result:
        return _error(404, "NOT_FOUND", f"No enrichment found for defect {defect_id}")
    return DefectEnrichmentRead.model_validate(result)


@router.post(
    "/enrich/{enrichment_id}/process",
    response_model=DefectEnrichmentRead,
    status_code=200,
)
async def process_enrichment_by_id(
    enrichment_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    provider: str | None = Query(None, description="Provider: template, edge_vlm"),
):
    """Manually process one enrichment job by ID.

    Query param `provider` selects the provider:
      - template: deterministic fallback
      - edge_vlm: uses env config (disabled by default)
      - omitted: uses env default
      - cloud_vlm: returns 501 (not implemented in Phase 10.1a)
    """
    try:
        vlm_provider = _resolve_provider(provider)
    except ValueError as exc:
        msg = str(exc)
        if "not implemented" in msg.lower():
            return _error(501, "PROVIDER_NOT_IMPLEMENTED", msg)
        return _error(400, "INVALID_PROVIDER", msg)
    except ProviderConfigError as exc:
        return _error(400, "PROVIDER_CONFIG_ERROR", str(exc))

    try:
        enrichment = await process_enrichment_job(
            db, enrichment_id, provider=vlm_provider,
            ws_manager=getattr(request.app.state, "ws_manager", None),
        )
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            return _error(404, "NOT_FOUND", msg)
        if "expected 'pending'" in msg:
            return _error(409, "ENRICHMENT_NOT_PENDING", msg)
        return _error(400, "INVALID_REQUEST", msg)

    return DefectEnrichmentRead.model_validate(enrichment)


@router.post(
    "/enrich/process-next",
    response_model=DefectEnrichmentRead,
    status_code=200,
)
async def process_next_enrichment(
    request: Request,
    db: AsyncSession = Depends(get_db),
    provider: str | None = Query(None, description="Provider: template, edge_vlm"),
):
    """Manually process the oldest pending enrichment job.

    Returns 404 if no pending jobs exist.
    """
    try:
        vlm_provider = _resolve_provider(provider)
    except ValueError as exc:
        msg = str(exc)
        if "not implemented" in msg.lower():
            return _error(501, "PROVIDER_NOT_IMPLEMENTED", msg)
        return _error(400, "INVALID_PROVIDER", msg)
    except ProviderConfigError as exc:
        return _error(400, "PROVIDER_CONFIG_ERROR", str(exc))

    enrichment = await process_next_pending_enrichment(
        db, provider=vlm_provider,
        ws_manager=getattr(request.app.state, "ws_manager", None),
    )
    if enrichment is None:
        return _error(404, "NO_PENDING_ENRICHMENT", "No pending enrichment jobs to process")

    return DefectEnrichmentRead.model_validate(enrichment)
