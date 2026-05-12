"""POST /api/edge/report — validation error contract tests.

Covers all error codes from API_CONTRACT.md §11.
"""

import copy
import json
from datetime import datetime


async def test_missing_required_field(async_client, dummy_jpeg, valid_meta):
    del valid_meta["line_id"]
    resp = await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(valid_meta)},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


async def test_schema_version_mismatch(async_client, dummy_jpeg, valid_meta):
    valid_meta["schema_version"] = "v2"
    resp = await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(valid_meta)},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "SCHEMA_MISMATCH"


async def test_duplicate_report(async_client, dummy_jpeg, valid_meta):
    payload = {
        "files": {"image": ("a.jpg", dummy_jpeg, "image/jpeg")},
        "data": {"meta": json.dumps(valid_meta)},
    }
    resp1 = await async_client.post("/api/edge/report", **payload)
    assert resp1.status_code == 200

    resp2 = await async_client.post("/api/edge/report", **payload)
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == "DUPLICATE_REPORT"


async def test_image_too_large(async_client, valid_meta):
    oversized = b"\xff\xd8\xff\xe0" + b"\x00" * (2 * 1024 * 1024)  # 2MB+ JPEG header
    resp = await async_client.post(
        "/api/edge/report",
        files={"image": ("big.jpg", oversized, "image/jpeg")},
        data={"meta": json.dumps(valid_meta)},
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


async def test_unsupported_media_type(async_client, dummy_jpeg, valid_meta):
    # FastAPI parses form parameters before the handler runs, so a non-multipart
    # request gets 422 from parameter validation, not 415 from the handler.
    # Our custom RequestValidationError handler returns {"error": {...}} format.
    resp = await async_client.post(
        "/api/edge/report",
        content=json.dumps({"meta": json.dumps(valid_meta)}),
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert "error" in body
    assert "code" in body["error"]


async def test_invalid_image_not_jpeg(async_client, valid_meta):
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    resp = await async_client.post(
        "/api/edge/report",
        files={"image": ("shot.png", png_bytes, "image/png")},
        data={"meta": json.dumps(valid_meta)},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_IMAGE"


async def test_bbox_exceeds_bounds(async_client, dummy_jpeg, valid_meta):
    valid_meta["bboxes"] = [{"x": 0.9, "y": 0.1, "w": 0.2, "h": 0.1}]  # x+w=1.1
    resp = await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(valid_meta)},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_naive_edge_ts(async_client, dummy_jpeg, valid_meta):
    valid_meta["edge_ts"] = datetime.now().isoformat()  # no tzinfo
    resp = await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(valid_meta)},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_error_format_is_not_detail(async_client, dummy_jpeg, valid_meta):
    """Error responses must use {"error": {...}}, not FastAPI's {"detail": "..."}."""
    del valid_meta["line_id"]
    resp = await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(valid_meta)},
    )
    body = resp.json()
    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]
    assert "detail" not in body


async def test_variant_new_valid(async_client, dummy_jpeg, valid_meta):
    """New variant values (2B_base etc.) should be accepted."""
    valid_meta["variant"] = "2B_base"
    resp = await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(valid_meta)},
    )
    assert resp.status_code == 200


async def test_variant_legacy_a(async_client, dummy_jpeg, valid_meta):
    """Legacy variant "A" should still be accepted (backward compat)."""
    valid_meta["variant"] = "A"
    resp = await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(valid_meta)},
    )
    assert resp.status_code == 200


async def test_variant_invalid(async_client, dummy_jpeg, valid_meta):
    """Invalid variant should return 400 VALIDATION_ERROR."""
    valid_meta["variant"] = "invalid"
    resp = await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(valid_meta)},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
