"""Phase 10.1b: auto-enqueue helper contract tests.

Covers:
  - config disabled -> returns None, creates no enrichment
  - enabled=true but auto_enqueue=false -> no enrichment
  - enabled=true and auto_enqueue=true -> creates pending enrichment
  - created row has correct fields
  - no provider call
  - duplicate prevention
  - empty bboxes -> no enqueue
  - confidence <= 0 -> no enqueue
  - fallback placeholder -> no enqueue
  - YOLO-owned defect fields unchanged
"""

import copy
import json
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.db import Base
from backend.app.models.defect import Defect
from backend.app.models.enrichment import DefectEnrichment
from backend.app.services.enrichment_config import EnrichmentConfig
from backend.app.services.enrichment_enqueue import maybe_auto_enqueue_enrichment


# ── DB fixtures ───────────────────────────────────────────────────────────────

_test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
_test_session = async_sessionmaker(_test_engine, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def _reset_db():
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _test_engine.dispose()


@pytest_asyncio.fixture
async def db():
    async with _test_session() as session:
        yield session


@pytest.fixture
def sample_defect_dict():
    """Valid defect data for creating test rows."""
    return {
        "image_url": "/static/defects/20260526/abc123.jpg",
        "line_id": "L1",
        "category": "metal_nut",
        "defect_type": "scratch",
        "severity": "high",
        "confidence": 0.95,
        "anomaly_score": 12.5,
        "bboxes": [{"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}],
        "description": "test scratch",
        "variant": "ort_2B",
        "edge_ts": datetime.now(timezone.utc),
        "pipeline_ms": {"efficientad": 12.0, "localizer": 25.0, "upload": 5.0},
        "schema_version": "v1",
    }


@pytest.fixture
def enabled_config():
    """Config with both enabled and auto_enqueue on."""
    return EnrichmentConfig(enabled=True, auto_enqueue=True)


@pytest.fixture
def disabled_config():
    """Config with defaults (both off)."""
    return EnrichmentConfig()


async def _insert_defect(db: AsyncSession, overrides: dict | None = None) -> Defect:
    """Insert and return a test defect."""
    data = {
        "image_url": "/static/defects/20260526/abc123.jpg",
        "line_id": "L1",
        "category": "metal_nut",
        "defect_type": "scratch",
        "severity": "high",
        "confidence": 0.95,
        "anomaly_score": 12.5,
        "bboxes": [{"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}],
        "description": "test scratch",
        "variant": "ort_2B",
        "edge_ts": datetime.now(timezone.utc),
        "pipeline_ms": {"efficientad": 12.0, "localizer": 25.0, "upload": 5.0},
        "schema_version": "v1",
    }
    if overrides:
        data.update(overrides)
    defect = Defect(**data)
    db.add(defect)
    await db.flush()
    await db.refresh(defect)
    return defect


# ── Tests: config disabled ────────────────────────────────────────────────────

async def test_disabled_config_returns_none(db, disabled_config):
    """With defaults (enabled=false), returns None and creates no enrichment."""
    defect = await _insert_defect(db)
    result = await maybe_auto_enqueue_enrichment(db, defect, config=disabled_config)
    assert result is None

    rows = (await db.execute(select(DefectEnrichment))).scalars().all()
    assert len(rows) == 0


# ── Tests: enabled but auto_enqueue off ───────────────────────────────────────

async def test_enabled_but_auto_enqueue_off(db):
    """enabled=true but auto_enqueue=false -> no enrichment."""
    defect = await _insert_defect(db)
    cfg = EnrichmentConfig(enabled=True, auto_enqueue=False)
    result = await maybe_auto_enqueue_enrichment(db, defect, config=cfg)
    assert result is None

    rows = (await db.execute(select(DefectEnrichment))).scalars().all()
    assert len(rows) == 0


# ── Tests: happy path ─────────────────────────────────────────────────────────

async def test_happy_path_creates_pending_enrichment(db, enabled_config):
    """enabled=true and auto_enqueue=true -> creates pending enrichment."""
    defect = await _insert_defect(db)
    result = await maybe_auto_enqueue_enrichment(db, defect, config=enabled_config)

    assert result is not None
    assert result.id > 0
    assert result.defect_id == defect.id
    assert result.status == "pending"
    assert result.provider == "edge_vlm"
    assert result.prompt_version == "phase10_1_obs_v1"
    assert result.provider_model == ""
    assert result.observation is None
    assert result.severity_reason is None
    assert result.raw_response is None
    assert result.completed_at is None


async def test_created_row_fields_correct(db, enabled_config):
    """Verify all fields on the created enrichment row."""
    defect = await _insert_defect(db)
    result = await maybe_auto_enqueue_enrichment(db, defect, config=enabled_config)

    assert result.error_message is None
    assert result.accepted_box_ids is None
    assert result.created_at is not None
    assert result.updated_at is not None


# ── Tests: duplicate prevention ───────────────────────────────────────────────

async def test_duplicate_prevention(db, enabled_config):
    """Second call for same defect+provider+prompt returns None, no duplicate row."""
    defect = await _insert_defect(db)

    first = await maybe_auto_enqueue_enrichment(db, defect, config=enabled_config)
    assert first is not None

    second = await maybe_auto_enqueue_enrichment(db, defect, config=enabled_config)
    assert second is None

    rows = (await db.execute(select(DefectEnrichment))).scalars().all()
    assert len(rows) == 1


# ── Tests: eligibility checks ─────────────────────────────────────────────────

async def test_empty_bboxes_no_enqueue(db, enabled_config):
    """Empty bboxes -> no enrichment."""
    defect = await _insert_defect(db, overrides={"bboxes": []})
    result = await maybe_auto_enqueue_enrichment(db, defect, config=enabled_config)
    assert result is None


async def test_zero_confidence_no_enqueue(db, enabled_config):
    """confidence=0 -> no enrichment."""
    defect = await _insert_defect(db, overrides={"confidence": 0.0})
    result = await maybe_auto_enqueue_enrichment(db, defect, config=enabled_config)
    assert result is None


async def test_negative_confidence_no_enqueue(db, enabled_config):
    """confidence < 0 -> no enrichment."""
    defect = await _insert_defect(db, overrides={"confidence": -0.5})
    result = await maybe_auto_enqueue_enrichment(db, defect, config=enabled_config)
    assert result is None


async def test_fallback_placeholder_no_enqueue(db, enabled_config):
    """Known fallback placeholder pattern -> no enrichment."""
    defect = await _insert_defect(db, overrides={
        "defect_type": "anomaly",
        "confidence": 0.0,
        "bboxes": [{"x": 0.3, "y": 0.3, "w": 0.4, "h": 0.4}],
    })
    result = await maybe_auto_enqueue_enrichment(db, defect, config=enabled_config)
    assert result is None


# ── Tests: YOLO-owned fields unchanged ────────────────────────────────────────

async def test_yolo_fields_unchanged(db, enabled_config):
    """Auto-enqueue must not mutate YOLO/ORT-owned defect fields."""
    defect = await _insert_defect(db)
    orig_category = defect.category
    orig_defect_type = defect.defect_type
    orig_confidence = defect.confidence
    orig_bboxes = copy.deepcopy(defect.bboxes)
    orig_severity = defect.severity
    orig_anomaly_score = defect.anomaly_score

    await maybe_auto_enqueue_enrichment(db, defect, config=enabled_config)

    assert defect.category == orig_category
    assert defect.defect_type == orig_defect_type
    assert defect.confidence == orig_confidence
    assert defect.bboxes == orig_bboxes
    assert defect.severity == orig_severity
    assert defect.anomaly_score == orig_anomaly_score
    # observation_source should not be set by auto-enqueue
    assert defect.observation_source is None


# ── Tests: custom config ──────────────────────────────────────────────────────

async def test_custom_provider_and_prompt(db):
    """Custom provider and prompt_version are used."""
    defect = await _insert_defect(db)
    cfg = EnrichmentConfig(
        enabled=True,
        auto_enqueue=True,
        provider="template",
        prompt_version="v2_custom",
    )
    result = await maybe_auto_enqueue_enrichment(db, defect, config=cfg)

    assert result is not None
    assert result.provider == "template"
    assert result.prompt_version == "v2_custom"


async def test_invalid_provider_returns_none(db):
    """Provider not in VALID_PROVIDERS -> returns None, no row, no DB error."""
    defect = await _insert_defect(db)
    cfg = EnrichmentConfig(enabled=True, auto_enqueue=True, provider="bad_provider")
    result = await maybe_auto_enqueue_enrichment(db, defect, config=cfg)

    assert result is None
    rows = (await db.execute(select(DefectEnrichment))).scalars().all()
    assert len(rows) == 0


async def test_empty_provider_returns_none(db):
    """Empty provider string -> returns None, no row."""
    defect = await _insert_defect(db)
    cfg = EnrichmentConfig(enabled=True, auto_enqueue=True, provider="")
    result = await maybe_auto_enqueue_enrichment(db, defect, config=cfg)

    assert result is None
    rows = (await db.execute(select(DefectEnrichment))).scalars().all()
    assert len(rows) == 0


async def test_config_none_loads_from_env(monkeypatch, db):
    """When config=None, loads from environment."""
    monkeypatch.setenv("ENRICHMENT_ENABLED", "true")
    monkeypatch.setenv("ENRICHMENT_AUTO_ENQUEUE", "true")

    defect = await _insert_defect(db)
    result = await maybe_auto_enqueue_enrichment(db, defect, config=None)

    assert result is not None
    assert result.status == "pending"


async def test_config_none_env_disabled(monkeypatch, db):
    """When config=None and env defaults are off, returns None."""
    monkeypatch.delenv("ENRICHMENT_ENABLED", raising=False)
    monkeypatch.delenv("ENRICHMENT_AUTO_ENQUEUE", raising=False)

    defect = await _insert_defect(db)
    result = await maybe_auto_enqueue_enrichment(db, defect, config=None)

    assert result is None


# ── Tests: multiple defects ───────────────────────────────────────────────────

async def test_different_defects_get_separate_enrichments(db, enabled_config):
    """Two different defects each get their own enrichment row."""
    d1 = await _insert_defect(db, overrides={"line_id": "L1", "edge_ts": datetime.now(timezone.utc)})
    d2 = await _insert_defect(db, overrides={"line_id": "L2", "edge_ts": datetime.now(timezone.utc)})

    r1 = await maybe_auto_enqueue_enrichment(db, d1, config=enabled_config)
    r2 = await maybe_auto_enqueue_enrichment(db, d2, config=enabled_config)

    assert r1 is not None
    assert r2 is not None
    assert r1.id != r2.id
    assert r1.defect_id == d1.id
    assert r2.defect_id == d2.id


# ── Tests: no provider call ───────────────────────────────────────────────────

async def test_no_provider_call(db, enabled_config, monkeypatch):
    """Auto-enqueue must not invoke any provider factory or provider.enrich()."""
    call_log = []

    def fake_get_provider(*args, **kwargs):
        call_log.append("get_provider")
        raise AssertionError("get_provider should not be called during auto-enqueue")

    monkeypatch.setattr(
        "backend.app.services.provider_factory.get_provider_from_env",
        fake_get_provider,
    )

    defect = await _insert_defect(db)
    result = await maybe_auto_enqueue_enrichment(db, defect, config=enabled_config)

    assert result is not None
    assert len(call_log) == 0
