"""Contract test fixtures — in-memory SQLite + httpx AsyncClient + sync TestClient.

Key design decisions (per guide):
  1. Lifespan triggered via sync TestClient context manager (for WS tests)
  2. DB isolation via in-memory engine + create_all/drop_all per test
  3. asyncio_mode = "auto" in pyproject.toml
"""

import copy
import io
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.db import Base, get_db
from backend.app.main import app

# ── test-scoped in-memory engine ─────────────────────────────────────────
_test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
_test_session = async_sessionmaker(_test_engine, expire_on_commit=False)


async def _override_get_db():
    async with _test_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = _override_get_db


# ── autouse: create/drop tables per test ─────────────────────────────────
@pytest_asyncio.fixture(autouse=True)
async def _reset_db():
    """Async autouse fixture — runs before every test (async or sync)."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _test_engine.dispose()


# ── fixtures ─────────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def async_client():
    """Async HTTP client (lifespan NOT triggered — fine for non-WS tests)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def sync_client():
    """Sync TestClient — lifespan IS triggered (ws_manager initialized)."""
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


@pytest.fixture
def dummy_jpeg() -> bytes:
    """Minimal 1x1 JPEG bytes."""
    img = Image.new("RGB", (1, 1), color=(128, 64, 32))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def valid_meta() -> dict:
    """Deep-copied valid DefectCreate dict — safe to mutate in tests."""
    return copy.deepcopy({
        "line_id": "L1",
        "category": "metal_nut",
        "defect_type": "scratch",
        "severity": "high",
        "confidence": 0.95,
        "anomaly_score": 12.5,
        "bboxes": [{"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}],
        "description": "test scratch",
        "variant": "A",
        "edge_ts": datetime.now(timezone.utc).isoformat(),
        "pipeline_ms": {
            "efficientad": 12.0,
            "fastsam": 45.0,
            "qwen3vl": 850.0,
        },
        "vlm_metrics": {
            "ttft_ms": 600.0,
            "decode_tps": 15.0,
            "prompt_tokens": 800,
            "output_tokens": 50,
            "rss_mb": 2500.0,
            "json_parse_ok": True,
        },
        "schema_version": "v1",
    })
