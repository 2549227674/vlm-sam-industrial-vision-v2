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
from backend.app.services.enrichment_ws_events import build_enrichment_event
from backend.app.services.image_resolver import resolve_image_path
from backend.app.services.provider_factory import get_provider_from_env
from backend.app.services.vlm_provider import (
    ProviderConfigError,
    ProviderUnavailableError,
    VlmEnrichmentInput,
    VlmProvider,
    VlmProviderError,
)

logger = logging.getLogger(__name__)


async def _emit(ws_manager: object | None, enrichment: DefectEnrichment, status: str) -> None:
    """Best-effort broadcast of enrichment lifecycle event.

    Awaits the broadcast directly for reliable delivery in test and production.
    Silently skips if ws_manager is None or broadcast fails.
    """
    if ws_manager is None:
        return
    try:
        event = build_enrichment_event(
            defect_id=enrichment.defect_id,
            enrichment_id=enrichment.id,
            status=status,  # type: ignore[arg-type]
            provider=enrichment.provider or "unknown",
            observation_source=enrichment.provider if status == "complete" else None,
            error_message=enrichment.error_message,
        )
        await ws_manager.broadcast("dashboard", event)  # type: ignore[union-attr]
    except Exception:
        logger.debug("Failed to emit enrichment event for %d", enrichment.id, exc_info=True)


def build_enrichment_input(
    defect: Defect,
    prompt_version: str = "phase10_1_obs_v1",
    resolved_image_path: str | None = None,
) -> VlmEnrichmentInput:
    """Build VlmEnrichmentInput from a Defect row.

    Args:
        defect: The Defect database row.
        prompt_version: The enrichment prompt version.
        resolved_image_path: Optional resolved absolute image path.
            If None, uses defect.image_url (may be relative URL).
    """
    return VlmEnrichmentInput(
        image_path=resolved_image_path or defect.image_url,
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
    ws_manager: object | None = None,
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
        await _emit(ws_manager, enrichment, "failed")
        return enrichment

    # Mark running
    enrichment.status = "running"
    await db.flush()

    # Resolve provider
    if provider is None:
        provider = get_provider_from_env()

    enrichment.provider = provider.provider_name
    enrichment.provider_model = provider.provider_model

    await _emit(ws_manager, enrichment, "running")

    # Resolve image path only for providers that need local files (edge_vlm)
    resolved_path: str | None = None
    if provider.provider_name == "edge_vlm":
        try:
            if defect.image_url:
                resolved = resolve_image_path(defect.image_url)
                resolved_path = str(resolved)
        except ValueError as exc:
            enrichment.status = "failed"
            enrichment.error_message = f"Image resolution failed: {exc}"
            enrichment.completed_at = datetime.now(timezone.utc)
            await db.flush()
            await _emit(ws_manager, enrichment, "failed")
            return enrichment

    # Build input with resolved path
    inp = build_enrichment_input(defect, enrichment.prompt_version, resolved_path)

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
    await _emit(ws_manager, enrichment, enrichment.status)
    return enrichment


async def process_next_pending_enrichment(
    db: AsyncSession,
    provider: VlmProvider | None = None,
    ws_manager: object | None = None,
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

    return await process_enrichment_job(db, result.id, provider=provider, ws_manager=ws_manager)
