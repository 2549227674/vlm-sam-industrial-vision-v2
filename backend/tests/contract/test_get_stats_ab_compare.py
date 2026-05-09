"""GET /api/stats — aggregation + AB comparison contract tests."""

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


async def test_stats_top_level_structure(async_client, dummy_jpeg, valid_meta):
    base = datetime.now(timezone.utc)
    await _post_defect(async_client, dummy_jpeg, valid_meta,
                       variant="A", edge_ts=base.isoformat())
    await _post_defect(async_client, dummy_jpeg, valid_meta,
                       variant="B", edge_ts=(base + timedelta(seconds=1)).isoformat())

    resp = await async_client.get("/api/stats")
    assert resp.status_code == 200
    stats = resp.json()
    assert set(stats.keys()) >= {"total", "by_category", "by_severity", "timeline", "ab_compare"}


async def test_timeline_format(async_client, dummy_jpeg, valid_meta):
    base = datetime.now(timezone.utc)
    await _post_defect(async_client, dummy_jpeg, valid_meta,
                       variant="A", edge_ts=base.isoformat())

    stats = (await async_client.get("/api/stats")).json()
    for item in stats["timeline"]:
        assert "ts" in item and "count" in item


async def test_ab_compare_both_variants(async_client, dummy_jpeg, valid_meta):
    base = datetime.now(timezone.utc) - timedelta(hours=1)
    for i in range(3):
        await _post_defect(
            async_client, dummy_jpeg, valid_meta,
            variant="A",
            edge_ts=(base + timedelta(seconds=i)).isoformat(),
        )
    for i in range(3):
        await _post_defect(
            async_client, dummy_jpeg, valid_meta,
            variant="B",
            edge_ts=(base + timedelta(seconds=10 + i)).isoformat(),
        )

    stats = (await async_client.get("/api/stats")).json()
    ab = stats["ab_compare"]

    for variant in ("A", "B"):
        assert variant in ab, f"Missing variant {variant} in ab_compare"
        v = ab[variant]
        assert set(v.keys()) >= {
            "count", "json_ok_rate", "avg_ttft_ms", "avg_decode_tps", "avg_rss_mb",
        }
        assert v["count"] == 3
        assert 0.0 <= v["json_ok_rate"] <= 1.0
