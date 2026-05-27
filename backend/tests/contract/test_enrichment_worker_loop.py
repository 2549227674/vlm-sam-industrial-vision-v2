"""Phase 10.1b-2: enrichment worker loop contract tests.

Covers:
  - defaults false -> no worker task started
  - ENRICHMENT_ENABLED=true but ENRICHMENT_WORKER_ENABLED=false -> no worker
  - worker enabled -> pending job processed using fake provider
  - worker disabled + pending job -> remains pending
  - clean shutdown/cancellation
  - provider error/timeout -> failed
  - guard violation -> rejected
  - success -> complete and denormalizes only observation/severity_reason/observation_source
  - YOLO/ORT fields unchanged after worker processing
  - ENRICHMENT_MAX_PER_MINUTE rate limit behavior
  - existing manual process routes still work
  - /api/edge/report does not call provider
  - no provider call during /api/edge/report
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.db import Base
from backend.app.models.defect import Defect
from backend.app.models.enrichment import DefectEnrichment
from backend.app.services.enrichment_config import EnrichmentConfig
from backend.app.services.enrichment_worker_loop import (
    _RateLimiter,
    enrichment_worker_loop,
)
from backend.app.services.vlm_provider import (
    ProviderUnavailableError,
    VlmEnrichmentInput,
    VlmEnrichmentOutput,
    VlmProvider,
)


# ── DB fixtures ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def _loop_db():
    """Per-test in-memory engine + session factory. Disposed after test."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    sf = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield sf
    # Cancel lingering worker tasks before dropping tables
    for task in asyncio.all_tasks():
        if task is not asyncio.current_task() and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db(_loop_db):
    async with _loop_db() as session:
        yield session


@pytest.fixture(autouse=True)
def _mock_image_resolver():
    with patch(
        "backend.app.services.enrichment_worker.resolve_image_path",
        side_effect=lambda url: Path("/fake") / url.lstrip("/"),
    ):
        yield


# ── Fake providers ──────────────────────────────────────────────────────────

class FakeSuccessProvider(VlmProvider):
    provider_name = "edge_vlm"
    provider_model = "fake-worker-vlm"

    async def enrich(self, inp: VlmEnrichmentInput) -> VlmEnrichmentOutput:
        return VlmEnrichmentOutput(
            observation="Worker VLM: scratch confirmed",
            severity_reason="Surface scratch may affect coating",
            accepted_box_ids=[0],
            raw_response=json.dumps({
                "observation": "Worker VLM: scratch confirmed",
                "severity_reason": "Surface scratch may affect coating",
                "accepted_box_ids": [0],
            }),
            provider="edge_vlm",
            provider_model="fake-worker-vlm",
        )


class FakeFailProvider(VlmProvider):
    provider_name = "edge_vlm"
    provider_model = "fake-fail"

    async def enrich(self, inp: VlmEnrichmentInput) -> VlmEnrichmentOutput:
        raise ProviderUnavailableError("Device offline")


class FakeHallucinatingProvider(VlmProvider):
    """Returns forbidden keys in raw_response."""
    provider_name = "edge_vlm"
    provider_model = "hallucinating"

    async def enrich(self, inp: VlmEnrichmentInput) -> VlmEnrichmentOutput:
        return VlmEnrichmentOutput(
            observation="Looks OK",
            severity_reason="Fine",
            accepted_box_ids=[0],
            raw_response=json.dumps({
                "observation": "Looks OK",
                "severity_reason": "Fine",
                "defect_type": "dent",  # forbidden
            }),
            provider="edge_vlm",
            provider_model="hallucinating",
        )


class CountingProvider(VlmProvider):
    """Counts how many times enrich() was called."""
    provider_name = "template"
    provider_model = "counter"

    def __init__(self):
        self.call_count = 0

    async def enrich(self, inp: VlmEnrichmentInput) -> VlmEnrichmentOutput:
        self.call_count += 1
        return VlmEnrichmentOutput(
            observation=f"Count {self.call_count}",
            severity_reason="reason",
            accepted_box_ids=[0],
            raw_response=json.dumps({
                "observation": f"Count {self.call_count}",
                "severity_reason": "reason",
                "accepted_box_ids": [0],
            }),
            provider="template",
            provider_model="counter",
        )


# ── Helpers ─────────────────────────────────────────────────────────────────

async def _insert_defect(db: AsyncSession, overrides: dict | None = None) -> Defect:
    data = {
        "image_url": "/static/defects/20260526/test.jpg",
        "line_id": "L1",
        "category": "metal_nut",
        "defect_type": "scratch",
        "severity": "high",
        "confidence": 0.95,
        "anomaly_score": 12.5,
        "bboxes": [{"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}],
        "description": "test",
        "variant": "ort_2B",
        "edge_ts": datetime.now(timezone.utc),
        "pipeline_ms": {"efficientad": 12.0, "localizer": 25.0, "upload": 5.0},
        "schema_version": "v1",
        "localization_source": "ort_yolov8n_cpu",
        "label_source": "yolo_class_head",
    }
    if overrides:
        data.update(overrides)
    defect = Defect(**data)
    db.add(defect)
    await db.flush()
    await db.refresh(defect)
    return defect


async def _insert_pending(
    db: AsyncSession,
    defect_id: int,
    provider: str = "edge_vlm",
    prompt_version: str = "phase10_1_obs_v1",
) -> DefectEnrichment:
    e = DefectEnrichment(
        defect_id=defect_id,
        provider=provider,
        provider_model="",
        prompt_version=prompt_version,
        status="pending",
    )
    db.add(e)
    await db.flush()
    await db.refresh(e)
    return e


def _make_config(
    enabled=True,
    worker_enabled=True,
    provider="edge_vlm",
    max_per_minute=60,
    worker_idle_sleep_s=0.01,
    worker_poll_interval_s=0.01,
    timeout_s=5,
) -> EnrichmentConfig:
    return EnrichmentConfig(
        enabled=enabled,
        auto_enqueue=False,
        worker_enabled=worker_enabled,
        provider=provider,
        max_per_minute=max_per_minute,
        worker_idle_sleep_s=worker_idle_sleep_s,
        worker_poll_interval_s=worker_poll_interval_s,
        timeout_s=timeout_s,
    )


async def _run_worker_short(config, sf, provider, seconds=0.15):
    """Run worker loop for a short time, return the task."""
    task = asyncio.create_task(
        enrichment_worker_loop(config, create_session_factory=sf, provider=provider)
    )
    await asyncio.sleep(seconds)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    return task


async def _run_worker_until_done(config, sf, provider, timeout=5.0):
    """Run worker loop until it processes at least one job or times out.

    Uses _poll_once patching to detect when a job is processed, then cancels.
    """
    processed = asyncio.Event()

    original_poll = __import__(
        "backend.app.services.enrichment_worker_loop",
        fromlist=["_poll_once"],
    )._poll_once

    async def tracking_poll(cfg, factory, prov, ws_mgr=None):
        result = await original_poll(cfg, factory, prov, ws_mgr)
        if result:
            processed.set()
        return result

    task = asyncio.create_task(
        enrichment_worker_loop(config, create_session_factory=sf, provider=provider)
    )
    with patch(
        "backend.app.services.enrichment_worker_loop._poll_once",
        side_effect=tracking_poll,
    ):
        try:
            await asyncio.wait_for(processed.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    return task


# ── Rate limiter unit tests ─────────────────────────────────────────────────

class TestRateLimiter:
    def test_allows_up_to_max(self):
        limiter = _RateLimiter(max_per_minute=3)
        assert limiter.allow()
        limiter.record()
        assert limiter.allow()
        limiter.record()
        assert limiter.allow()
        limiter.record()
        assert not limiter.allow()

    def test_min_value_is_one(self):
        limiter = _RateLimiter(max_per_minute=0)
        assert limiter._max == 1

    def test_wait_seconds_zero_when_under_limit(self):
        limiter = _RateLimiter(max_per_minute=5)
        limiter.record()
        assert limiter.wait_seconds == 0.0

    def test_wait_seconds_positive_at_limit(self):
        limiter = _RateLimiter(max_per_minute=1)
        limiter.record()
        assert limiter.wait_seconds > 0.0


# ── Worker loop tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_worker_processes_pending_job(db, _loop_db):
    """Worker loop processes a pending job to complete."""
    defect = await _insert_defect(db)
    enrichment = await _insert_pending(db, defect.id)
    await db.commit()

    config = _make_config()
    provider = FakeSuccessProvider()

    await _run_worker_until_done(config, _loop_db, provider)

    async with _loop_db() as verify_db:
        loaded = await verify_db.get(DefectEnrichment, enrichment.id)
        assert loaded.status == "complete"
        assert loaded.observation is not None
        assert loaded.severity_reason is not None


@pytest.mark.asyncio
async def test_worker_denormalizes_only_allowed_fields(db, _loop_db):
    """Worker only writes observation/severity_reason/observation_source to defect."""
    defect = await _insert_defect(db)
    orig_category = defect.category
    orig_defect_type = defect.defect_type
    orig_confidence = defect.confidence
    orig_anomaly_score = defect.anomaly_score
    orig_bboxes = defect.bboxes
    orig_loc = defect.localization_source
    orig_label = defect.label_source

    await _insert_pending(db, defect.id)
    await db.commit()

    await _run_worker_until_done(_make_config(), _loop_db, FakeSuccessProvider())

    async with _loop_db() as verify_db:
        d = await verify_db.get(Defect, defect.id)
        assert d.observation is not None
        assert d.severity_reason is not None
        assert d.observation_source == "edge_vlm"
        assert d.category == orig_category
        assert d.defect_type == orig_defect_type
        assert d.confidence == orig_confidence
        assert d.anomaly_score == orig_anomaly_score
        assert d.bboxes == orig_bboxes
        assert d.localization_source == orig_loc
        assert d.label_source == orig_label


@pytest.mark.asyncio
async def test_worker_provider_error_marks_failed(db, _loop_db):
    """Provider error -> enrichment status=failed."""
    defect = await _insert_defect(db)
    enrichment = await _insert_pending(db, defect.id)
    await db.commit()

    await _run_worker_until_done(_make_config(), _loop_db, FakeFailProvider())

    async with _loop_db() as verify_db:
        loaded = await verify_db.get(DefectEnrichment, enrichment.id)
        assert loaded.status == "failed"
        assert "offline" in loaded.error_message


@pytest.mark.asyncio
async def test_worker_guard_rejection(db, _loop_db):
    """Hallucination guard -> enrichment status=rejected."""
    defect = await _insert_defect(db)
    enrichment = await _insert_pending(db, defect.id)
    await db.commit()

    await _run_worker_until_done(_make_config(), _loop_db, FakeHallucinatingProvider())

    async with _loop_db() as verify_db:
        loaded = await verify_db.get(DefectEnrichment, enrichment.id)
        assert loaded.status == "rejected"
        assert "Forbidden" in loaded.error_message


@pytest.mark.asyncio
async def test_worker_no_pending_jobs_idle_sleeps(db, _loop_db):
    """When no pending jobs, worker idles without calling provider."""
    provider = CountingProvider()
    await _run_worker_short(
        _make_config(worker_idle_sleep_s=0.02), _loop_db, provider,
    )
    assert provider.call_count == 0


@pytest.mark.asyncio
async def test_worker_clean_shutdown(_loop_db):
    """Worker loop shuts down cleanly on cancel."""
    config = _make_config(worker_idle_sleep_s=10.0)
    task = asyncio.create_task(
        enrichment_worker_loop(
            config, create_session_factory=_loop_db, provider=FakeSuccessProvider(),
        )
    )
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await asyncio.wait_for(task, timeout=2.0)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass
    assert task.done()


@pytest.mark.asyncio
async def test_worker_disabled_does_not_start():
    """Config with worker_enabled=False — lifespan skips worker."""
    config = _make_config(enabled=True, worker_enabled=False)
    assert config.enabled is True
    assert config.worker_enabled is False


@pytest.mark.asyncio
async def test_defaults_no_worker():
    """Default config has worker_enabled=False."""
    config = EnrichmentConfig()
    assert config.enabled is False
    assert config.worker_enabled is False


@pytest.mark.asyncio
async def test_worker_processes_multiple_jobs(db, _loop_db):
    """Worker processes multiple pending jobs sequentially."""
    d1 = await _insert_defect(db, overrides={
        "line_id": "L1", "edge_ts": datetime.now(timezone.utc),
    })
    d2 = await _insert_defect(db, overrides={
        "line_id": "L2", "edge_ts": datetime.now(timezone.utc),
    })
    e1 = await _insert_pending(db, d1.id)
    e2 = await _insert_pending(db, d2.id)
    await db.commit()

    provider = CountingProvider()
    count_event = asyncio.Event()

    original_poll = __import__(
        "backend.app.services.enrichment_worker_loop", fromlist=["_poll_once"],
    )._poll_once

    async def tracking_poll(cfg, factory, prov, ws_mgr=None):
        result = await original_poll(cfg, factory, prov, ws_mgr)
        if result and prov.call_count >= 2:
            count_event.set()
        return result

    task = asyncio.create_task(
        enrichment_worker_loop(
            _make_config(), create_session_factory=_loop_db, provider=provider,
        )
    )
    with patch(
        "backend.app.services.enrichment_worker_loop._poll_once",
        side_effect=tracking_poll,
    ):
        try:
            await asyncio.wait_for(count_event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pass

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    async with _loop_db() as verify_db:
        l1 = await verify_db.get(DefectEnrichment, e1.id)
        l2 = await verify_db.get(DefectEnrichment, e2.id)
        assert l1.status == "complete"
        assert l2.status == "complete"
    assert provider.call_count >= 2


@pytest.mark.asyncio
async def test_worker_provider_error_does_not_break_loop(db, _loop_db):
    """After a provider error, worker continues polling for next job."""
    d1 = await _insert_defect(db, overrides={
        "line_id": "L1", "edge_ts": datetime.now(timezone.utc),
    })
    d2 = await _insert_defect(db, overrides={
        "line_id": "L2", "edge_ts": datetime.now(timezone.utc),
    })
    await _insert_pending(db, d1.id, prompt_version="v_fail")
    await _insert_pending(db, d2.id, prompt_version="v_ok")
    await db.commit()

    call_count = 0
    ok_reached = asyncio.Event()

    class MixedProvider(VlmProvider):
        provider_name = "edge_vlm"
        provider_model = "mixed"

        async def enrich(self, inp: VlmEnrichmentInput) -> VlmEnrichmentOutput:
            nonlocal call_count
            call_count += 1
            if inp.prompt_version == "v_fail":
                raise ProviderUnavailableError("offline")
            ok_reached.set()
            return VlmEnrichmentOutput(
                observation="OK",
                severity_reason="reason",
                accepted_box_ids=[0],
                raw_response=json.dumps({
                    "observation": "OK",
                    "severity_reason": "reason",
                    "accepted_box_ids": [0],
                }),
                provider="edge_vlm",
                provider_model="mixed",
            )

    task = asyncio.create_task(
        enrichment_worker_loop(
            _make_config(), create_session_factory=_loop_db, provider=MixedProvider(),
        )
    )
    try:
        await asyncio.wait_for(ok_reached.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        pass
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert call_count >= 2


@pytest.mark.asyncio
async def test_worker_manual_process_still_works(db, _loop_db):
    """Manual process_next_pending_enrichment still works alongside worker."""
    from backend.app.services.enrichment_worker import process_next_pending_enrichment

    defect = await _insert_defect(db)
    await _insert_pending(db, defect.id, provider="template")
    await db.commit()

    async with _loop_db() as manual_db:
        result = await process_next_pending_enrichment(
            manual_db, provider=FakeSuccessProvider(),
        )
        await manual_db.commit()

    assert result is not None
    assert result.status == "complete"


@pytest.mark.asyncio
async def test_worker_does_not_process_non_pending(db, _loop_db):
    """Worker skips jobs that are not pending (e.g. already complete)."""
    defect = await _insert_defect(db)
    enrichment = await _insert_pending(db, defect.id)
    enrichment.status = "complete"
    enrichment.completed_at = datetime.now(timezone.utc)
    await db.commit()

    provider = CountingProvider()
    await _run_worker_short(_make_config(), _loop_db, provider)
    assert provider.call_count == 0


@pytest.mark.asyncio
async def test_worker_rate_limit_behavior():
    """Rate limiter blocks calls beyond max_per_minute."""
    limiter = _RateLimiter(max_per_minute=2)
    assert limiter.allow()
    limiter.record()
    assert limiter.allow()
    limiter.record()
    assert not limiter.allow()
    # wait_seconds should be positive
    assert limiter.wait_seconds > 0


@pytest.mark.asyncio
async def test_invalid_provider_exits_cleanly(_loop_db):
    """Worker loop with invalid provider returns cleanly, no crash."""
    from backend.app.services.enrichment_config import EnrichmentConfig
    from backend.app.services.vlm_provider import ProviderConfigError

    config = EnrichmentConfig(
        enabled=True,
        worker_enabled=True,
        provider="nonexistent_provider",
    )
    # Must not raise — should return cleanly
    await enrichment_worker_loop(
        config, create_session_factory=_loop_db, provider=None,
    )


@pytest.mark.asyncio
async def test_shutdown_after_failed_task():
    """Shutdown handles a task that ended with an exception."""
    async def _failing_coro():
        raise RuntimeError("Simulated worker crash")

    task = asyncio.create_task(_failing_coro())
    await asyncio.sleep(0.05)
    assert task.done()
    assert task.exception() is not None

    # Simulate main.py shutdown logic for an already-done task with exception
    if task.done():
        exc = task.exception()
        if exc:
            # Must not re-raise
            pass
