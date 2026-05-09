"""POST /api/edge/report — happy path contract tests."""

import json
import re
from datetime import datetime, timezone


async def test_post_report_returns_200(async_client, dummy_jpeg, valid_meta):
    resp = await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(valid_meta)},
    )
    assert resp.status_code == 200


async def test_response_has_exactly_three_fields(async_client, dummy_jpeg, valid_meta):
    resp = await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(valid_meta)},
    )
    body = resp.json()
    assert set(body.keys()) == {"id", "image_url", "server_ts"}


async def test_image_url_format(async_client, dummy_jpeg, valid_meta):
    resp = await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(valid_meta)},
    )
    image_url = resp.json()["image_url"]
    assert re.match(r"^/static/defects/\d{8}/[0-9a-f]+\.jpg$", image_url)


async def test_server_ts_is_aware(async_client, dummy_jpeg, valid_meta):
    resp = await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(valid_meta)},
    )
    ts = datetime.fromisoformat(resp.json()["server_ts"])
    assert ts.tzinfo is not None


async def test_defect_persisted_in_db(async_client, dummy_jpeg, valid_meta):
    await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(valid_meta)},
    )
    list_resp = await async_client.get("/api/defects")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1


async def test_image_file_saved(async_client, dummy_jpeg, valid_meta):
    from pathlib import Path

    resp = await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(valid_meta)},
    )
    image_url = resp.json()["image_url"]  # e.g. /static/defects/20260509/abc.jpg
    static_root = Path(__file__).resolve().parent.parent.parent / "static"
    filepath = static_root / image_url.lstrip("/static/")
    assert filepath.exists()
