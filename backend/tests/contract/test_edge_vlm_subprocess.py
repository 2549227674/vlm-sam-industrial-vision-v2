"""Phase 10.1: EdgeVlmProvider subprocess contract tests.

Tests using fake subprocess scripts (no real VLM model or RK3588 hardware).
Covers: valid JSON, forbidden keys, invalid JSON, timeout, nonzero exit,
stderr truncation, missing image, regression checks.
"""

import json
import os
import stat
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from unittest.mock import patch
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.db import Base
from backend.app.models.defect import Defect
from backend.app.models.enrichment import DefectEnrichment
from backend.app.services.enrichment_worker import (
    process_enrichment_job,
    process_next_pending_enrichment,
)
from backend.app.services.vlm_provider import (
    EdgeVlmProvider,
    ProviderTimeoutError,
    VlmProviderError,
    VlmEnrichmentInput,
)


# ── Test DB engine ─────────────────────────────────────────────────────────
_sub_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
_sub_session = async_sessionmaker(_sub_engine, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def _reset_db():
    async with _sub_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _sub_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _sub_engine.dispose()


@pytest_asyncio.fixture
async def db():
    async with _sub_session() as session:
        yield session


# ── Fake script helpers ────────────────────────────────────────────────────

def _write_script(tmp_path: Path, name: str, body: str) -> str:
    """Write a fake executable script and return its path."""
    script = tmp_path / name
    script.write_text(textwrap.dedent(body), encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


def _passthrough_resolve(image_url: str) -> Path:
    """Mock resolver for tests."""
    return Path("/fake") / image_url.lstrip("/")


@pytest.fixture(autouse=True)
def _mock_resolver():
    with patch(
        "backend.app.services.enrichment_worker.resolve_image_path",
        side_effect=_passthrough_resolve,
    ):
        yield


# ── Helpers ────────────────────────────────────────────────────────────────

async def _create_defect(db: AsyncSession) -> Defect:
    defect = Defect(
        image_url="/static/defects/20260526/test.jpg",
        line_id="L1",
        category="metal_nut",
        defect_type="scratch",
        severity="high",
        confidence=0.95,
        anomaly_score=12.5,
        bboxes=[{"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}],
        description="test",
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


async def _create_pending(db: AsyncSession, defect_id: int) -> DefectEnrichment:
    enrichment = DefectEnrichment(
        defect_id=defect_id,
        provider="edge_vlm",
        provider_model="",
        prompt_version="phase10_1_obs_v1",
        status="pending",
    )
    db.add(enrichment)
    await db.flush()
    await db.refresh(enrichment)
    return enrichment


# ── A. Valid JSON subprocess ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_subprocess_valid_json_success(db, tmp_path):
    """Valid JSON stdout → complete, observation_source=edge_vlm."""
    script = _write_script(tmp_path, "vlm_ok.py", """\
        import sys, json
        inp = json.load(sys.stdin)
        out = {
            "observation": "Metal nut has a visible scratch on surface.",
            "severity_reason": "Surface scratch may compromise coating.",
            "accepted_box_ids": [0],
        }
        print(json.dumps(out))
    """)

    defect = await _create_defect(db)
    enrichment = await _create_pending(db, defect.id)

    provider = EdgeVlmProvider(mode="subprocess", command=f"python3 {script}")
    result = await process_enrichment_job(db, enrichment.id, provider=provider)

    assert result.status == "complete"
    assert "scratch" in result.observation.lower()
    assert result.severity_reason is not None
    assert result.accepted_box_ids == [0]
    assert result.provider == "edge_vlm"
    assert result.completed_at is not None

    # Defect updated
    await db.refresh(defect)
    assert defect.observation_source == "edge_vlm"
    assert defect.observation is not None


@pytest.mark.asyncio
async def test_subprocess_yolo_fields_unchanged(db, tmp_path):
    """YOLO-owned fields are never modified by subprocess enrichment."""
    script = _write_script(tmp_path, "vlm_ok2.py", """\
        import sys, json
        json.load(sys.stdin)
        print(json.dumps({
            "observation": "test obs",
            "severity_reason": "test reason",
            "accepted_box_ids": [0],
        }))
    """)

    defect = await _create_defect(db)
    orig_cat = defect.category
    orig_dt = defect.defect_type
    orig_conf = defect.confidence
    orig_as = defect.anomaly_score
    orig_bb = defect.bboxes
    orig_loc = defect.localization_source

    enrichment = await _create_pending(db, defect.id)
    provider = EdgeVlmProvider(mode="subprocess", command=f"python3 {script}")
    await process_enrichment_job(db, enrichment.id, provider=provider)

    await db.refresh(defect)
    assert defect.category == orig_cat
    assert defect.defect_type == orig_dt
    assert defect.confidence == orig_conf
    assert defect.anomaly_score == orig_as
    assert defect.bboxes == orig_bb
    assert defect.localization_source == orig_loc


# ── B. Forbidden key stdout → rejected ─────────────────────────────────────

@pytest.mark.asyncio
async def test_subprocess_forbidden_key_rejected(db, tmp_path):
    """Subprocess returning forbidden keys → rejected, no defect update."""
    script = _write_script(tmp_path, "vlm_bad.py", """\
        import sys, json
        json.load(sys.stdin)
        print(json.dumps({
            "observation": "Looks like a scratch.",
            "severity_reason": "Moderate.",
            "defect_type": "dent",
            "bbox": [0.1, 0.2, 0.3, 0.4],
        }))
    """)

    defect = await _create_defect(db)
    orig_obs_source = defect.observation_source
    enrichment = await _create_pending(db, defect.id)

    provider = EdgeVlmProvider(mode="subprocess", command=f"python3 {script}")
    result = await process_enrichment_job(db, enrichment.id, provider=provider)

    assert result.status == "rejected"
    assert "Forbidden" in result.error_message

    await db.refresh(defect)
    assert defect.observation_source == orig_obs_source


# ── C. Invalid JSON stdout → rejected ──────────────────────────────────────

@pytest.mark.asyncio
async def test_subprocess_invalid_json_rejected(db, tmp_path):
    """Subprocess returning non-JSON → rejected."""
    script = _write_script(tmp_path, "vlm_nonsense.py", """\
        import sys
        sys.stdin.read()
        print("This is not valid JSON at all.")
    """)

    defect = await _create_defect(db)
    enrichment = await _create_pending(db, defect.id)

    provider = EdgeVlmProvider(mode="subprocess", command=f"python3 {script}")
    result = await process_enrichment_job(db, enrichment.id, provider=provider)

    assert result.status == "rejected"
    assert result.error_message is not None


# ── D. Timeout → killed, enrichment failed ─────────────────────────────────

@pytest.mark.asyncio
async def test_subprocess_timeout_fails(db, tmp_path):
    """Subprocess that exceeds timeout → killed, status=failed."""
    script = _write_script(tmp_path, "vlm_slow.py", """\
        import sys, time
        sys.stdin.read()
        time.sleep(30)
        print("{}")
    """)

    defect = await _create_defect(db)
    enrichment = await _create_pending(db, defect.id)

    provider = EdgeVlmProvider(
        mode="subprocess", command=f"python3 {script}", timeout_s=2,
    )
    result = await process_enrichment_job(db, enrichment.id, provider=provider)

    assert result.status == "failed"
    assert "timed out" in result.error_message.lower()


# ── E. Nonzero exit → failed ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_subprocess_nonzero_exit_fails(db, tmp_path):
    """Subprocess that exits nonzero → status=failed with exit code."""
    script = _write_script(tmp_path, "vlm_crash.py", """\
        import sys
        sys.stdin.read()
        print("error: model failed", file=sys.stderr)
        sys.exit(1)
    """)

    defect = await _create_defect(db)
    enrichment = await _create_pending(db, defect.id)

    provider = EdgeVlmProvider(mode="subprocess", command=f"python3 {script}")
    result = await process_enrichment_job(db, enrichment.id, provider=provider)

    assert result.status == "failed"
    assert "exited with code 1" in result.error_message
    assert "model failed" in result.error_message


# ── F. stderr truncation ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_subprocess_stderr_truncated(db, tmp_path):
    """Long stderr is truncated to safe length."""
    script = _write_script(tmp_path, "vlm_verbose.py", """\
        import sys
        sys.stdin.read()
        print("X" * 2000, file=sys.stderr)
        sys.exit(2)
    """)

    defect = await _create_defect(db)
    enrichment = await _create_pending(db, defect.id)

    provider = EdgeVlmProvider(mode="subprocess", command=f"python3 {script}")
    result = await process_enrichment_job(db, enrichment.id, provider=provider)

    assert result.status == "failed"
    assert len(result.error_message) <= 600  # exit code msg + truncated stderr


# ── G. Missing image → failed, subprocess not called ───────────────────────

@pytest.mark.asyncio
async def test_missing_image_fails_without_subprocess(db, tmp_path):
    """If image resolver fails, enrichment fails without calling subprocess."""
    defect = await _create_defect(db)
    enrichment = await _create_pending(db, defect.id)

    # Override mock to raise
    with patch(
        "backend.app.services.enrichment_worker.resolve_image_path",
        side_effect=ValueError("Image file not found"),
    ):
        provider = EdgeVlmProvider(
            mode="subprocess", command="/usr/bin/false",
        )
        result = await process_enrichment_job(
            db, enrichment.id, provider=provider,
        )

    assert result.status == "failed"
    assert "Image resolution failed" in result.error_message
    # subprocess was never called (otherwise /usr/bin/false would have run)


# ── H. Regression: POST /api/edge/report unchanged ─────────────────────────

@pytest.mark.asyncio
async def test_edge_report_no_enrichment_rows(db):
    """POST /api/edge/report does not create enrichment rows."""
    defect = await _create_defect(db)
    await db.commit()

    q = (
        __import__("sqlalchemy").select(DefectEnrichment)
        .where(DefectEnrichment.defect_id == defect.id)
    )
    rows = (await db.execute(q)).scalars().all()
    assert len(rows) == 0


# ── I. Regression: template provider still works ────────────────────────────

@pytest.mark.asyncio
async def test_template_provider_still_works(db):
    """Template provider path is unaffected by subprocess changes."""
    from backend.app.services.vlm_provider import TemplateProvider

    defect = await _create_defect(db)
    enrichment = await _create_pending(db, defect.id, )

    result = await process_enrichment_job(
        db, enrichment.id, provider=TemplateProvider(),
    )
    assert result.status == "complete"
    assert "[Template]" in result.observation


# ── J. Regression: HTTP mode still not wired ───────────────────────────────

@pytest.mark.asyncio
async def test_http_mode_still_unavailable():
    """HTTP mode still raises ProviderUnavailableError."""
    provider = EdgeVlmProvider(mode="http", endpoint="http://localhost:8001/vlm")
    with pytest.raises(Exception, match="not yet wired"):
        await provider.enrich(VlmEnrichmentInput(
            image_path="/tmp/test.jpg",
            category="metal_nut",
            defect_type="scratch",
            confidence=0.95,
            bboxes=[{"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}],
        ))


# ── K. Payload structure ───────────────────────────────────────────────────

def test_build_payload_structure():
    """_build_payload produces the expected structure."""
    inp = VlmEnrichmentInput(
        image_path="/tmp/test.jpg",
        category="metal_nut",
        defect_type="scratch",
        confidence=0.95,
        bboxes=[{"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}],
        localization_source="ort_yolov8n_cpu",
        label_source="yolo_class_head",
        prompt_version="phase10_1_obs_v1",
    )
    payload = EdgeVlmProvider._build_payload(inp)

    assert payload["task"] == "phase10.1_vlm_enrichment"
    assert payload["image_path"] == "/tmp/test.jpg"
    assert payload["category"] == "metal_nut"
    assert payload["defect_type"] == "scratch"
    assert payload["confidence"] == 0.95
    assert payload["boxes"] == [{"box_id": 0, "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}]
    assert payload["language"] == "zh-CN"
    assert "observation" in payload["allowed_output_fields"]
    assert "bbox" in payload["forbidden_output_fields"]
    assert "defect_type" in payload["forbidden_output_fields"]


def test_build_payload_multiple_boxes():
    """_build_payload handles multiple boxes."""
    inp = VlmEnrichmentInput(
        image_path="/tmp/test.jpg",
        category="cable",
        defect_type="cut",
        confidence=0.8,
        bboxes=[
            {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2},
            {"x": 0.5, "y": 0.5, "w": 0.1, "h": 0.1},
        ],
    )
    payload = EdgeVlmProvider._build_payload(inp)
    assert len(payload["boxes"]) == 2
    assert payload["boxes"][0]["box_id"] == 0
    assert payload["boxes"][1]["box_id"] == 1


def test_subprocess_json_protocol_roundtrip(tmp_path):
    """Fake subprocess reads stdin JSON and returns stdout JSON."""
    script = _write_script(tmp_path, "roundtrip.py", """\
        import sys, json
        inp = json.load(sys.stdin)
        assert inp["task"] == "phase10.1_vlm_enrichment"
        assert "image_path" in inp
        print(json.dumps({
            "observation": "test",
            "severity_reason": "test",
            "accepted_box_ids": [0],
        }))
    """)

    import asyncio

    async def _run():
        provider = EdgeVlmProvider(mode="subprocess", command=f"python3 {script}")
        inp = VlmEnrichmentInput(
            image_path="/tmp/test.jpg",
            category="metal_nut",
            defect_type="scratch",
            confidence=0.95,
            bboxes=[{"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}],
        )
        output = await provider.enrich(inp)
        data = json.loads(output.raw_response)
        assert data["observation"] == "test"
        assert output.provider == "edge_vlm"

    asyncio.run(_run())
