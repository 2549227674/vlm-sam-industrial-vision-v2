# Phase 10.1: Enrichment worker service — processes pending enrichment jobs.
#
# Functions are small and testable. Provider injection for tests.
# Worker is NOT auto-started; must be explicitly invoked or wired in a future step.

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.defect import Defect
from backend.app.models.enrichment import DefectEnrichment
from backend.app.services.enrichment_guard import (
    EnrichmentValidationError,
    validate_vlm_output,
)
from backend.app.services.provider_factory import get_provider_from_env
from backend.app.services.vlm_provider import (
    ProviderConfigError,
    ProviderUnavailableError,
    VlmEnrichmentInput,
    VlmProvider,
    VlmProviderError,
)

logger = logging.getLogger(__name__)


def build_enrichment_input(
    defect: Defect,
    prompt_version: str = "phase10_1_obs_v1",
) -> VlmEnrichmentInput:
    """Build VlmEnrichmentInput from a Defect row."""
    return VlmEnrichmentInput(
        image_path=defect.image_url,
        category=defect.category,
        defect_type=defect.defect_type,
        confidence=defect.confidence,
        bboxes=defect.bboxes or [],
        localization_source=defect.localization_source,
        label_source=defect.label_source,
        prompt_version=prompt_version,
    )


async def process_enrichment_job(
    db: AsyncSession,
    enrichment_id: int,
    provider: VlmProvider | None = None,
) -> DefectEnrichment:
    """Process a single enrichment job through the provider + guard pipeline.

    Args:
        db: Async database session.
        enrichment_id: ID of the enrichment row to process.
        provider: VlmProvider instance. If None, uses get_provider_from_env().

    Returns:
        The updated DefectEnrichment row.

    Raises:
        ValueError: If enrichment not found or not in pending status.
    """
    enrichment = await db.get(DefectEnrichment, enrichment_id)
    if enrichment is None:
        raise ValueError(f"Enrichment {enrichment_id} not found")

    if enrichment.status != "pending":
        raise ValueError(
            f"Enrichment {enrichment_id} has status '{enrichment.status}', "
            f"expected 'pending'"
        )

    # Load related defect
    defect = await db.get(Defect, enrichment.defect_id)
    if defect is None:
        enrichment.status = "failed"
        enrichment.error_message = f"Defect {enrichment.defect_id} not found"
        enrichment.completed_at = datetime.now(timezone.utc)
        await db.flush()
        return enrichment

    # Mark running
    enrichment.status = "running"
    await db.flush()

    # Resolve provider
    if provider is None:
        provider = get_provider_from_env()

    enrichment.provider = provider.provider_name
    enrichment.provider_model = provider.provider_model

    # Build input
    inp = build_enrichment_input(defect, enrichment.prompt_version)

    try:
        # Call provider
        output = await provider.enrich(inp)

        # Validate through guard
        validated = validate_vlm_output(
            output.raw_response,
            input_box_ids=inp.box_ids,
        )

        # Success — update enrichment
        enrichment.status = "complete"
        enrichment.observation = validated["observation"]
        enrichment.severity_reason = validated["severity_reason"]
        enrichment.accepted_box_ids = validated["accepted_box_ids"]
        enrichment.raw_response = output.raw_response
        enrichment.error_message = None
        enrichment.completed_at = datetime.now(timezone.utc)

        # Denormalize to defect (only mutable fields)
        defect.observation = validated["observation"]
        defect.severity_reason = validated["severity_reason"]
        defect.observation_source = provider.provider_name

    except EnrichmentValidationError as exc:
        enrichment.status = "rejected"
        enrichment.error_message = str(exc)[:512]
        enrichment.completed_at = datetime.now(timezone.utc)
        logger.warning(
            "Enrichment %d rejected: %s", enrichment_id, exc,
        )

    except (ProviderUnavailableError, ProviderConfigError, VlmProviderError) as exc:
        enrichment.status = "failed"
        enrichment.error_message = str(exc)[:512]
        enrichment.completed_at = datetime.now(timezone.utc)
        logger.warning(
            "Enrichment %d provider error: %s", enrichment_id, exc,
        )

    except Exception as exc:
        enrichment.status = "failed"
        enrichment.error_message = f"Unexpected error: {type(exc).__name__}"
        enrichment.completed_at = datetime.now(timezone.utc)
        logger.exception(
            "Enrichment %d unexpected error", enrichment_id,
        )

    await db.flush()
    return enrichment


async def process_next_pending_enrichment(
    db: AsyncSession,
    provider: VlmProvider | None = None,
) -> DefectEnrichment | None:
    """Pick the oldest pending enrichment and process it.

    Returns:
        The processed DefectEnrichment, or None if no pending jobs exist.
    """
    q = (
        select(DefectEnrichment)
        .where(DefectEnrichment.status == "pending")
        .order_by(DefectEnrichment.created_at.asc())
        .limit(1)
    )
    result = (await db.execute(q)).scalar_one_or_none()
    if result is None:
        return None

    return await process_enrichment_job(db, result.id, provider=provider)
