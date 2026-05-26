"""Phase 10.1 Step 2c: enrichment worker service contract tests.

Tests for backend/app/services/enrichment_worker.py:
  - build_enrichment_input
  - process_enrichment_job (success / rejected / failed)
  - process_next_pending_enrichment
  - YOLO-owned field protection
  - Guard integration
  - No-op on non-pending jobs
"""

import json
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.db import Base, get_db
from backend.app.main import app
from backend.app.models.defect import Defect
from backend.app.models.enrichment import DefectEnrichment
from backend.app.services.enrichment_worker import (
    build_enrichment_input,
    process_enrichment_job,
    process_next_pending_enrichment,
)
from backend.app.services.vlm_provider import (
    ProviderUnavailableError,
    VlmEnrichmentInput,
    VlmEnrichmentOutput,
    VlmProvider,
)

# ── Test DB engine ─────────────────────────────────────────────────────────
_worker_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
_worker_session_factory = async_sessionmaker(
    _worker_engine, expire_on_commit=False,
)


@pytest_asyncio.fixture(autouse=True)
async def _reset_worker_db():
    """Create/drop tables for worker tests."""
    async with _worker_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _worker_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _worker_engine.dispose()


@pytest_asyncio.fixture
async def db():
    """Direct DB session for worker tests."""
    async with _worker_session_factory() as session:
        yield session


# ── Helpers ────────────────────────────────────────────────────────────────

async def _create_defect_row(db: AsyncSession) -> Defect:
    """Insert a defect directly and return it."""
    defect = Defect(
        image_url="/static/defects/20260526/test.jpg",
        line_id="L1",
        category="metal_nut",
        defect_type="scratch",
        severity="high",
        confidence=0.95,
        anomaly_score=12.5,
        bboxes=[{"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}],
        description="test scratch",
        variant="ort_2B",
        edge_ts=datetime.now(timezone.utc),
        pipeline_ms={"efficientad": 12.0, "localizer": 25.0, "upload": 5.0},
        schema_version="v1",
        localization_source="ort_yolov8n_cpu",
        label_source="yolo_class_head",
    )
    db.add(defect)
    await db.flush()
    await db.refresh(defect)
    return defect


async def _create_pending_enrichment(
    db: AsyncSession,
    defect_id: int,
    provider: str = "edge_vlm",
    prompt_version: str = "phase10_1_obs_v1",
) -> DefectEnrichment:
    """Insert a pending enrichment row directly and return it."""
    enrichment = DefectEnrichment(
        defect_id=defect_id,
        provider=provider,
        provider_model="",
        prompt_version=prompt_version,
        status="pending",
    )
    db.add(enrichment)
    await db.flush()
    await db.refresh(enrichment)
    return enrichment


class FakeEdgeVlmProvider(VlmProvider):
    """Fake edge_vlm provider for tests — returns valid output."""
    provider_name = "edge_vlm"
    provider_model = "fake-edge-vlm"

    async def enrich(self, inp: VlmEnrichmentInput) -> VlmEnrichmentOutput:
        return VlmEnrichmentOutput(
            observation="Edge VLM: scratch detected on metal nut surface.",
            severity_reason="Surface scratch may affect coating integrity.",
            accepted_box_ids=[0],
            raw_response=json.dumps({
                "observation": "Edge VLM: scratch detected on metal nut surface.",
                "severity_reason": "Surface scratch may affect coating integrity.",
                "accepted_box_ids": [0],
            }),
            provider="edge_vlm",
            provider_model="fake-edge-vlm",
        )


class ForbiddenKeyProvider(VlmProvider):
    """Fake provider that returns raw_response with forbidden keys."""
    provider_name = "edge_vlm"
    provider_model = "hallucinating"

    async def enrich(self, inp: VlmEnrichmentInput) -> VlmEnrichmentOutput:
        raw = json.dumps({
            "observation": "Looks like a scratch.",
            "severity_reason": "Moderate damage.",
            "defect_type": "dent",
            "bbox": [0.1, 0.2, 0.3, 0.4],
        })
        return VlmEnrichmentOutput(
            observation="Looks like a scratch.",
            severity_reason="Moderate damage.",
            accepted_box_ids=[0],
            raw_response=raw,
            provider="edge_vlm",
            provider_model="hallucinating",
        )


class InvalidJsonProvider(VlmProvider):
    """Fake provider that returns non-JSON raw_response."""
    provider_name = "edge_vlm"
    provider_model = "broken"

    async def enrich(self, inp: VlmEnrichmentInput) -> VlmEnrichmentOutput:
        return VlmEnrichmentOutput(
            observation="not used",
            severity_reason="not used",
            accepted_box_ids=[],
            raw_response="This is not valid JSON at all.",
            provider="edge_vlm",
            provider_model="broken",
        )


class UnavailableProvider(VlmProvider):
    """Fake provider that raises ProviderUnavailableError."""
    provider_name = "edge_vlm"
    provider_model = "offline"

    async def enrich(self, inp: VlmEnrichmentInput) -> VlmEnrichmentOutput:
        raise ProviderUnavailableError("Edge VLM device is offline.")


class UnexpectedErrorProvider(VlmProvider):
    """Fake provider that raises an unexpected exception."""
    provider_name = "edge_vlm"
    provider_model = "crasher"

    async def enrich(self, inp: VlmEnrichmentInput) -> VlmEnrichmentOutput:
        raise RuntimeError("Something completely unexpected happened")


# ── build_enrichment_input ─────────────────────────────────────────────────

def test_build_enrichment_input_basic():
    """build_enrichment_input maps defect fields correctly."""
    defect = Defect(
        image_url="/static/defects/20260526/test.jpg",
        category="metal_nut",
        defect_type="scratch",
        confidence=0.95,
        bboxes=[{"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}],
        localization_source="ort_yolov8n_cpu",
        label_source="yolo_class_head",
    )
    inp = build_enrichment_input(defect, prompt_version="phase10_1_obs_v1")
    assert inp.image_path == "/static/defects/20260526/test.jpg"
    assert inp.category == "metal_nut"
    assert inp.defect_type == "scratch"
    assert inp.confidence == 0.95
    assert inp.bboxes == [{"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}]
    assert inp.localization_source == "ort_yolov8n_cpu"
    assert inp.label_source == "yolo_class_head"
    assert inp.prompt_version == "phase10_1_obs_v1"
    assert inp.box_ids == [0]


def test_build_enrichment_input_empty_bboxes():
    """build_enrichment_input handles empty bboxes."""
    defect = Defect(
        image_url="/tmp/test.jpg",
        category="cable",
        defect_type="cut",
        confidence=0.8,
        bboxes=[],
    )
    inp = build_enrichment_input(defect)
    assert inp.bboxes == []
    assert inp.box_ids == []


def test_build_enrichment_input_none_bboxes():
    """build_enrichment_input handles None bboxes."""
    defect = Defect(
        image_url="/tmp/test.jpg",
        category="cable",
        defect_type="cut",
        confidence=0.8,
        bboxes=None,
    )
    inp = build_enrichment_input(defect)
    assert inp.bboxes == []


# ── A. Success path with TemplateProvider ──────────────────────────────────

@pytest.mark.asyncio
async def test_success_template_provider(db):
    """TemplateProvider processes pending → complete, updates defect fields."""
    from backend.app.services.vlm_provider import TemplateProvider

    defect = await _create_defect_row(db)
    enrichment = await _create_pending_enrichment(db, defect.id, provider="template")

    result = await process_enrichment_job(
        db, enrichment.id, provider=TemplateProvider(),
    )

    assert result.status == "complete"
    assert "[Template]" in result.observation
    assert len(result.observation) > 0
    assert "[Template]" in result.severity_reason
    assert result.accepted_box_ids == [0]
    assert result.error_message is None
    assert result.completed_at is not None
    assert result.provider == "template"

    # Defect updated
    await db.refresh(defect)
    assert defect.observation == result.observation
    assert defect.severity_reason == result.severity_reason
    assert defect.observation_source == "template"


# ── B. Success path with fake edge_vlm provider ───────────────────────────

@pytest.mark.asyncio
async def test_success_edge_vlm_provider(db):
    """Fake edge_vlm provider processes pending → complete."""
    defect = await _create_defect_row(db)
    enrichment = await _create_pending_enrichment(db, defect.id)

    result = await process_enrichment_job(
        db, enrichment.id, provider=FakeEdgeVlmProvider(),
    )

    assert result.status == "complete"
    assert "Edge VLM" in result.observation
    assert result.accepted_box_ids == [0]
    assert result.completed_at is not None
    assert result.provider == "edge_vlm"

    # Defect updated with edge_vlm source
    await db.refresh(defect)
    assert defect.observation == result.observation
    assert defect.severity_reason == result.severity_reason
    assert defect.observation_source == "edge_vlm"


@pytest.mark.asyncio
async def test_success_yolo_fields_unchanged(db):
    """YOLO-owned fields are never modified on success."""
    defect = await _create_defect_row(db)
    orig_category = defect.category
    orig_defect_type = defect.defect_type
    orig_confidence = defect.confidence
    orig_anomaly_score = defect.anomaly_score
    orig_bboxes = defect.bboxes
    orig_loc_source = defect.localization_source
    orig_label_source = defect.label_source

    enrichment = await _create_pending_enrichment(db, defect.id)
    await process_enrichment_job(
        db, enrichment.id, provider=FakeEdgeVlmProvider(),
    )

    await db.refresh(defect)
    assert defect.category == orig_category
    assert defect.defect_type == orig_defect_type
    assert defect.confidence == orig_confidence
    assert defect.anomaly_score == orig_anomaly_score
    assert defect.bboxes == orig_bboxes
    assert defect.localization_source == orig_loc_source
    assert defect.label_source == orig_label_source


# ── C. Rejected path: forbidden key ───────────────────────────────────────

@pytest.mark.asyncio
async def test_rejected_forbidden_key(db):
    """Provider returning forbidden keys → status=rejected."""
    defect = await _create_defect_row(db)
    orig_obs_source = defect.observation_source
    enrichment = await _create_pending_enrichment(db, defect.id)

    result = await process_enrichment_job(
        db, enrichment.id, provider=ForbiddenKeyProvider(),
    )

    assert result.status == "rejected"
    assert "Forbidden" in result.error_message
    assert result.completed_at is not None

    # Defect observation_source NOT updated to edge_vlm
    await db.refresh(defect)
    assert defect.observation_source == orig_obs_source


@pytest.mark.asyncio
async def test_rejected_forbidden_key_yolo_fields_unchanged(db):
    """YOLO-owned fields unchanged when enrichment is rejected."""
    defect = await _create_defect_row(db)
    orig_category = defect.category
    orig_defect_type = defect.defect_type
    orig_confidence = defect.confidence

    enrichment = await _create_pending_enrichment(db, defect.id)
    await process_enrichment_job(
        db, enrichment.id, provider=ForbiddenKeyProvider(),
    )

    await db.refresh(defect)
    assert defect.category == orig_category
    assert defect.defect_type == orig_defect_type
    assert defect.confidence == orig_confidence


# ── D. Rejected path: invalid JSON ────────────────────────────────────────

@pytest.mark.asyncio
async def test_rejected_invalid_json(db):
    """Provider returning non-JSON → status=rejected."""
    defect = await _create_defect_row(db)
    orig_obs_source = defect.observation_source
    enrichment = await _create_pending_enrichment(db, defect.id)

    result = await process_enrichment_job(
        db, enrichment.id, provider=InvalidJsonProvider(),
    )

    assert result.status == "rejected"
    assert result.error_message is not None
    assert result.completed_at is not None

    # Defect observation_source NOT updated
    await db.refresh(defect)
    assert defect.observation_source == orig_obs_source


# ── E. Failed path: ProviderUnavailableError ──────────────────────────────

@pytest.mark.asyncio
async def test_failed_provider_unavailable(db):
    """ProviderUnavailableError → status=failed."""
    defect = await _create_defect_row(db)
    orig_obs_source = defect.observation_source
    enrichment = await _create_pending_enrichment(db, defect.id)

    result = await process_enrichment_job(
        db, enrichment.id, provider=UnavailableProvider(),
    )

    assert result.status == "failed"
    assert "offline" in result.error_message
    assert result.completed_at is not None

    # Defect observation_source NOT updated
    await db.refresh(defect)
    assert defect.observation_source == orig_obs_source


@pytest.mark.asyncio
async def test_failed_provider_unavailable_yolo_fields_unchanged(db):
    """YOLO-owned fields unchanged when provider is unavailable."""
    defect = await _create_defect_row(db)
    orig_category = defect.category
    orig_defect_type = defect.defect_type
    orig_confidence = defect.confidence
    orig_bboxes = defect.bboxes

    enrichment = await _create_pending_enrichment(db, defect.id)
    await process_enrichment_job(
        db, enrichment.id, provider=UnavailableProvider(),
    )

    await db.refresh(defect)
    assert defect.category == orig_category
    assert defect.defect_type == orig_defect_type
    assert defect.confidence == orig_confidence
    assert defect.bboxes == orig_bboxes


# ── E2. Failed path: unexpected Exception ──────────────────────────────────

@pytest.mark.asyncio
async def test_failed_unexpected_error(db):
    """Unexpected exception → status=failed, safe error message."""
    defect = await _create_defect_row(db)
    enrichment = await _create_pending_enrichment(db, defect.id)

    result = await process_enrichment_job(
        db, enrichment.id, provider=UnexpectedErrorProvider(),
    )

    assert result.status == "failed"
    assert "Unexpected error" in result.error_message
    assert "RuntimeError" in result.error_message
    assert "Something completely unexpected" not in result.error_message
    assert result.completed_at is not None


# ── F. No pending job ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_pending_returns_none(db):
    """process_next_pending_enrichment returns None when no pending jobs."""
    result = await process_next_pending_enrichment(db)
    assert result is None


@pytest.mark.asyncio
async def test_no_pending_after_complete_returns_none(db):
    """After processing the only pending job, returns None."""
    defect = await _create_defect_row(db)
    await _create_pending_enrichment(db, defect.id, provider="template")

    from backend.app.services.vlm_provider import TemplateProvider
    first = await process_next_pending_enrichment(
        db, provider=TemplateProvider(),
    )
    assert first is not None
    assert first.status == "complete"

    second = await process_next_pending_enrichment(db)
    assert second is None


# ── G. Non-pending job raises ValueError ───────────────────────────────────

@pytest.mark.asyncio
async def test_non_pending_raises_value_error(db):
    """Processing a complete enrichment raises ValueError."""
    defect = await _create_defect_row(db)
    enrichment = await _create_pending_enrichment(db, defect.id, provider="template")
    enrichment.status = "complete"
    enrichment.completed_at = datetime.now(timezone.utc)
    await db.flush()

    with pytest.raises(ValueError, match="expected 'pending'"):
        await process_enrichment_job(db, enrichment.id)


@pytest.mark.asyncio
async def test_already_running_raises_value_error(db):
    """Processing a running enrichment raises ValueError."""
    defect = await _create_defect_row(db)
    enrichment = await _create_pending_enrichment(db, defect.id)
    enrichment.status = "running"
    await db.flush()

    with pytest.raises(ValueError, match="expected 'pending'"):
        await process_enrichment_job(db, enrichment.id)


@pytest.mark.asyncio
async def test_nonexistent_enrichment_raises_value_error(db):
    """Processing a nonexistent enrichment raises ValueError."""
    with pytest.raises(ValueError, match="not found"):
        await process_enrichment_job(db, 99999)


# ── H. Provider None uses env disabled provider → fails ───────────────────

@pytest.mark.asyncio
async def test_none_provider_uses_env_default(monkeypatch, db):
    """With default env, provider=None → disabled EdgeVlmProvider → failed."""
    monkeypatch.delenv("ENRICHMENT_PROVIDER", raising=False)
    monkeypatch.delenv("EDGE_VLM_MODE", raising=False)

    defect = await _create_defect_row(db)
    orig_obs_source = defect.observation_source
    enrichment = await _create_pending_enrichment(db, defect.id)

    result = await process_enrichment_job(db, enrichment.id)

    assert result.status == "failed"
    assert result.error_message is not None
    assert "disabled" in result.error_message.lower()
    assert result.completed_at is not None

    # Defect NOT mutated
    await db.refresh(defect)
    assert defect.observation_source == orig_obs_source


# ── I. Upload path non-blocking regression ─────────────────────────────────

@pytest.mark.asyncio
async def test_no_auto_enrichment_on_defect_insert(db):
    """Creating a defect does NOT create enrichment rows automatically."""
    defect = await _create_defect_row(db)
    await db.commit()

    q = (
        select(DefectEnrichment)
        .where(DefectEnrichment.defect_id == defect.id)
    )
    enrichments = (await db.execute(q)).scalars().all()
    assert len(enrichments) == 0


# ── process_next_pending_enrichment picks oldest ──────────────────────────

@pytest.mark.asyncio
async def test_picks_oldest_pending(db):
    """process_next_pending_enrichment picks the oldest pending job."""
    from backend.app.services.vlm_provider import TemplateProvider

    defect = await _create_defect_row(db)
    e1 = await _create_pending_enrichment(
        db, defect.id, provider="template", prompt_version="v1",
    )
    e2 = await _create_pending_enrichment(
        db, defect.id, provider="template", prompt_version="v2",
    )

    result = await process_next_pending_enrichment(
        db, provider=TemplateProvider(),
    )
    assert result is not None
    assert result.id == e1.id
    assert result.status == "complete"


# ── Status transitions are persisted ───────────────────────────────────────

@pytest.mark.asyncio
async def test_status_transitions_persisted(db):
    """All status changes are committed to DB."""
    from backend.app.services.vlm_provider import TemplateProvider

    defect = await _create_defect_row(db)
    enrichment = await _create_pending_enrichment(
        db, defect.id, provider="template",
    )

    # Process
    await process_enrichment_job(
        db, enrichment.id, provider=TemplateProvider(),
    )

    # Reload from DB
    loaded = await db.get(DefectEnrichment, enrichment.id)
    assert loaded.status == "complete"
    assert loaded.completed_at is not None
    assert loaded.observation is not None
    assert loaded.severity_reason is not None


# ── Guard integration: raw_response validated ──────────────────────────────

@pytest.mark.asyncio
async def test_guard_validates_raw_response(db):
    """Worker uses guard to validate raw_response, not output fields directly."""
    defect = await _create_defect_row(db)
    enrichment = await _create_pending_enrichment(db, defect.id)

    result = await process_enrichment_job(
        db, enrichment.id, provider=FakeEdgeVlmProvider(),
    )

    # If guard passed, raw_response should be stored
    assert result.raw_response is not None
    data = json.loads(result.raw_response)
    assert "observation" in data
    assert "severity_reason" in data


@pytest.mark.asyncio
async def test_enrichment_observation_matches_guard_output(db):
    """Enrichment observation matches what the guard returned (stripped)."""
    defect = await _create_defect_row(db)
    enrichment = await _create_pending_enrichment(db, defect.id)

    result = await process_enrichment_job(
        db, enrichment.id, provider=FakeEdgeVlmProvider(),
    )

    # Guard strips whitespace — verify the stored value matches
    assert result.observation == result.observation.strip()
    assert result.severity_reason == result.severity_reason.strip()
