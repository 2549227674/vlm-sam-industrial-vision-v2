# Phase 10.1b: Auto-enqueue helper — creates pending enrichment job after defect insert.
#
# Conservative eligibility: false negatives OK, false positives avoided.
# Does NOT call provider. Does NOT process job. Does NOT mutate YOLO-owned fields.

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.defect import Defect
from backend.app.models.enrichment import DefectEnrichment, VALID_PROVIDERS
from backend.app.services.enrichment_config import EnrichmentConfig, load_enrichment_config

logger = logging.getLogger(__name__)


def _is_eligible_for_enrichment(defect: Defect) -> bool:
    """Check if a defect is eligible for auto-enqueue.

    Conservative: false negatives acceptable, false positives avoided.
    Returns False for:
      - empty bboxes
      - confidence <= 0
      - fallback placeholder (defect_type='anomaly', confidence==0, single 0.3/0.3/0.4/0.4 bbox)
    """
    # Must have at least one bbox
    if not defect.bboxes:
        return False

    # Must have positive confidence
    if defect.confidence <= 0:
        return False

    # Reject known fallback placeholder pattern
    if (
        defect.defect_type == "anomaly"
        and defect.confidence == 0
        and len(defect.bboxes) == 1
        and abs(defect.bboxes[0].get("x", 0) - 0.3) < 0.01
        and abs(defect.bboxes[0].get("y", 0) - 0.3) < 0.01
        and abs(defect.bboxes[0].get("w", 0) - 0.4) < 0.01
        and abs(defect.bboxes[0].get("h", 0) - 0.4) < 0.01
    ):
        return False

    return True


async def maybe_auto_enqueue_enrichment(
    db: AsyncSession,
    defect: Defect,
    config: EnrichmentConfig | None = None,
) -> DefectEnrichment | None:
    """Create a pending enrichment job if auto-enqueue is enabled and defect is eligible.

    Args:
        db: Async database session (same session as defect insert).
        defect: The freshly inserted/flushed Defect row.
        config: EnrichmentConfig. If None, loads from environment.

    Returns:
        The created DefectEnrichment row, or None if:
          - auto-enqueue is disabled
          - defect is ineligible
          - duplicate already exists (returns None, does not raise)

    Does NOT call provider. Does NOT process the job.
    Does NOT mutate YOLO-owned defect fields (category, defect_type, confidence, bboxes, etc.).
    """
    if config is None:
        config = load_enrichment_config()

    # Gate 1: enrichment subsystem must be enabled
    if not config.enabled:
        return None

    # Gate 2: auto_enqueue must be on
    if not config.auto_enqueue:
        return None

    # Gate 3: provider must be valid (DB CheckConstraint allows only VALID_PROVIDERS)
    if config.provider not in VALID_PROVIDERS:
        logger.warning(
            "Invalid enrichment provider %r, skipping auto-enqueue for defect %d",
            config.provider, defect.id,
        )
        return None

    # Gate 4: defect must be eligible
    if not _is_eligible_for_enrichment(defect):
        return None

    # Gate 5: duplicate prevention — any existing row for same defect+provider+prompt
    dup_q = select(DefectEnrichment).where(
        DefectEnrichment.defect_id == defect.id,
        DefectEnrichment.provider == config.provider,
        DefectEnrichment.prompt_version == config.prompt_version,
    )
    existing = (await db.execute(dup_q)).scalar_one_or_none()
    if existing is not None:
        return None

    # Create pending job — no provider call, no processing
    enrichment = DefectEnrichment(
        defect_id=defect.id,
        provider=config.provider,
        provider_model="",
        prompt_version=config.prompt_version,
        status="pending",
    )
    db.add(enrichment)
    await db.flush()
    await db.refresh(enrichment)

    logger.info(
        "Auto-enqueued enrichment %d for defect %d (provider=%s, prompt=%s)",
        enrichment.id, defect.id, config.provider, config.prompt_version,
    )
    return enrichment
