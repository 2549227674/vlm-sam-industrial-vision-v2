# Phase 10.1: Enrichment API routes — manual trigger + status query.

import os

from fastapi import APIRouter, Depends, Request
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

router = APIRouter(prefix="/api", tags=["enrichment"])

_DEFAULT_PROVIDER = os.environ.get("ENRICHMENT_PROVIDER", "edge_vlm")
_DEFAULT_PROMPT_VERSION = os.environ.get("ENRICHMENT_PROMPT_VERSION", "phase10_1_obs_v1")


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
