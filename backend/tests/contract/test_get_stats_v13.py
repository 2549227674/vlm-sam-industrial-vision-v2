"""GET /api/stats — v1.3 pipeline_ms stage keys contract tests.

Tests for:
  - avg_pipeline_ms includes all six stage keys (old + new)
  - New pipeline_ms stages (localizer/upload) are aggregated correctly
  - Old pipeline_ms stages (fastsam/qwen3vl) still aggregated for backward compat
"""

import copy
import json
from datetime import datetime, timedelta, timezone


async def _post_defect(client, jpeg, base_meta, **overrides):
    meta = copy.deepcopy(base_meta)
    meta.update(overrides)
    resp = await client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", jpeg, "image/jpeg")},
        data={"meta": json.dumps(meta)},
    )
    assert resp.status_code == 200, resp.text


async def test_avg_pipeline_ms_has_all_six_keys(async_client, dummy_jpeg, valid_meta):
    """avg_pipeline_ms must include efficientad, fastsam, qwen3vl, localizer, upload, enrichment."""
    base = datetime.now(timezone.utc)
    await _post_defect(async_client, dummy_jpeg, valid_meta,
                       edge_ts=base.isoformat())

    stats = (await async_client.get("/api/stats")).json()
    avg = stats["avg_pipeline_ms"]
    for key in ("efficientad", "fastsam", "qwen3vl", "localizer", "upload", "enrichment"):
        assert key in avg, f"Missing key '{key}' in avg_pipeline_ms"
        assert isinstance(avg[key], (int, float))


async def test_new_pipeline_stages_aggregated(async_client, dummy_jpeg, valid_meta):
    """New pipeline_ms keys (localizer/upload) are correctly averaged."""
    base = datetime.now(timezone.utc) - timedelta(hours=1)

    # Post two defects with new stage keys
    meta1 = copy.deepcopy(valid_meta)
    meta1["pipeline_ms"] = {"efficientad": 10.0, "localizer": 20.0, "upload": 5.0}
    meta1["edge_ts"] = base.isoformat()
    await _post_defect(async_client, dummy_jpeg, meta1)

    meta2 = copy.deepcopy(valid_meta)
    meta2["pipeline_ms"] = {"efficientad": 20.0, "localizer": 40.0, "upload": 10.0}
    meta2["edge_ts"] = (base + timedelta(seconds=1)).isoformat()
    await _post_defect(async_client, dummy_jpeg, meta2)

    stats = (await async_client.get("/api/stats")).json()
    avg = stats["avg_pipeline_ms"]

    assert avg["efficientad"] == 15.0
    assert avg["localizer"] == 30.0
    assert avg["upload"] == 7.5
    # Old keys should be 0 when not present in data
    assert avg["fastsam"] == 0
    assert avg["qwen3vl"] == 0


async def test_old_pipeline_stages_still_work(async_client, dummy_jpeg, valid_meta):
    """Old pipeline_ms keys (fastsam/qwen3vl) are correctly averaged."""
    base = datetime.now(timezone.utc) - timedelta(hours=1)
    await _post_defect(async_client, dummy_jpeg, valid_meta,
                       edge_ts=base.isoformat())

    stats = (await async_client.get("/api/stats")).json()
    avg = stats["avg_pipeline_ms"]

    # valid_meta uses fastsam=45.0, qwen3vl=850.0
    assert avg["fastsam"] > 0
    assert avg["qwen3vl"] > 0
