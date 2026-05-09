"""GET /api/defects — pagination, filtering, sorting contract tests."""

import copy
import json
from datetime import datetime, timedelta, timezone


async def _post_defect(client, jpeg, base_meta, **overrides):
    """Post a single defect with field overrides. Returns the created id."""
    meta = copy.deepcopy(base_meta)
    meta.update(overrides)
    resp = await client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", jpeg, "image/jpeg")},
        data={"meta": json.dumps(meta)},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def test_pagination(async_client, dummy_jpeg, valid_meta):
    base = datetime.now(timezone.utc) - timedelta(hours=1)
    for i in range(5):
        await _post_defect(
            async_client, dummy_jpeg, valid_meta,
            edge_ts=(base + timedelta(seconds=i)).isoformat(),
        )

    resp = await async_client.get("/api/defects", params={"page": 1, "page_size": 2})
    body = resp.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2


async def test_filter_by_category(async_client, dummy_jpeg, valid_meta):
    base = datetime.now(timezone.utc) - timedelta(hours=1)
    await _post_defect(async_client, dummy_jpeg, valid_meta,
                       category="metal_nut", edge_ts=base.isoformat())
    await _post_defect(async_client, dummy_jpeg, valid_meta,
                       category="metal_nut", edge_ts=(base + timedelta(seconds=1)).isoformat())
    await _post_defect(async_client, dummy_jpeg, valid_meta,
                       category="pill", edge_ts=(base + timedelta(seconds=2)).isoformat())

    resp = await async_client.get("/api/defects", params={"category": "pill"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["category"] == "pill"


async def test_filter_by_severity(async_client, dummy_jpeg, valid_meta):
    base = datetime.now(timezone.utc) - timedelta(hours=1)
    await _post_defect(async_client, dummy_jpeg, valid_meta,
                       severity="low", edge_ts=base.isoformat())
    await _post_defect(async_client, dummy_jpeg, valid_meta,
                       severity="high", edge_ts=(base + timedelta(seconds=1)).isoformat())

    resp = await async_client.get("/api/defects", params={"severity": "low"})
    assert resp.json()["total"] == 1


async def test_filter_by_variant(async_client, dummy_jpeg, valid_meta):
    base = datetime.now(timezone.utc) - timedelta(hours=1)
    await _post_defect(async_client, dummy_jpeg, valid_meta,
                       variant="A", edge_ts=base.isoformat())
    await _post_defect(async_client, dummy_jpeg, valid_meta,
                       variant="B", edge_ts=(base + timedelta(seconds=1)).isoformat())

    resp = await async_client.get("/api/defects", params={"variant": "B"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["variant"] == "B"


async def test_sort_desc_default(async_client, dummy_jpeg, valid_meta):
    """Default sort is -edge_ts (descending)."""
    base = datetime.now(timezone.utc) - timedelta(hours=1)
    await _post_defect(async_client, dummy_jpeg, valid_meta,
                       edge_ts=base.isoformat())
    await _post_defect(async_client, dummy_jpeg, valid_meta,
                       edge_ts=(base + timedelta(seconds=10)).isoformat())

    resp = await async_client.get("/api/defects")
    items = resp.json()["items"]
    t0 = datetime.fromisoformat(items[0]["edge_ts"])
    t1 = datetime.fromisoformat(items[1]["edge_ts"])
    assert t0 >= t1


async def test_sort_ascending(async_client, dummy_jpeg, valid_meta):
    base = datetime.now(timezone.utc) - timedelta(hours=1)
    await _post_defect(async_client, dummy_jpeg, valid_meta,
                       edge_ts=base.isoformat())
    await _post_defect(async_client, dummy_jpeg, valid_meta,
                       edge_ts=(base + timedelta(seconds=10)).isoformat())

    resp = await async_client.get("/api/defects", params={"sort": "edge_ts"})
    items = resp.json()["items"]
    t0 = datetime.fromisoformat(items[0]["edge_ts"])
    t1 = datetime.fromisoformat(items[1]["edge_ts"])
    assert t0 <= t1


async def test_until_strict_boundary(async_client, dummy_jpeg, valid_meta):
    """until=T must NOT include records with edge_ts == T (strictly less than)."""
    boundary = datetime(2026, 5, 9, 12, 0, 0, tzinfo=timezone.utc)
    await _post_defect(async_client, dummy_jpeg, valid_meta,
                       edge_ts=boundary.isoformat())

    # exact boundary → excluded
    resp = await async_client.get("/api/defects", params={"until": boundary.isoformat()})
    assert resp.json()["total"] == 0

    # boundary + 1s → included
    resp2 = await async_client.get(
        "/api/defects",
        params={"until": (boundary + timedelta(seconds=1)).isoformat()},
    )
    assert resp2.json()["total"] == 1
