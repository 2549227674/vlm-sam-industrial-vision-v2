"""POST /api/edge/report — v1.3 contract tests (Phase 10 localization refactor).

Tests for:
  - New optional source fields accepted
  - New pipeline_ms stage keys (localizer/upload) accepted
  - Old pipeline_ms stage keys (fastsam/qwen3vl) still accepted (backward compat)
  - Source fields persisted and returned in GET /api/defects
"""

import copy
import json
from datetime import datetime, timezone


async def test_post_with_v13_source_fields(async_client, dummy_jpeg, valid_meta):
    """v1.3 source fields accepted and persisted."""
    meta = copy.deepcopy(valid_meta)
    meta["localization_source"] = "yolov8n_detect_rknn"
    meta["label_source"] = "yolo_class_head"
    meta["observation_source"] = "template"
    meta["defect_family"] = "surface_damage"
    meta["observation"] = "Metal nut with visible scratch on edge"
    meta["severity_reason"] = "Scratch is shallow, low functional impact"

    resp = await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(meta)},
    )
    assert resp.status_code == 200


async def test_post_with_new_pipeline_ms_stages(async_client, dummy_jpeg, valid_meta):
    """New pipeline_ms keys (localizer/upload) accepted."""
    meta = copy.deepcopy(valid_meta)
    meta["pipeline_ms"] = {
        "efficientad": 12.0,
        "localizer": 25.0,
        "upload": 5.0,
    }

    resp = await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(meta)},
    )
    assert resp.status_code == 200


async def test_post_with_old_pipeline_ms_stages_still_accepted(async_client, dummy_jpeg, valid_meta):
    """Old pipeline_ms keys (fastsam/qwen3vl) still accepted for backward compat."""
    meta = copy.deepcopy(valid_meta)
    meta["pipeline_ms"] = {
        "efficientad": 12.0,
        "fastsam": 45.0,
        "qwen3vl": 850.0,
    }

    resp = await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(meta)},
    )
    assert resp.status_code == 200


async def test_post_without_source_fields_still_works(async_client, dummy_jpeg, valid_meta):
    """Omitting all v1.3 source fields still works (backward compat)."""
    resp = await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(valid_meta)},
    )
    assert resp.status_code == 200


async def test_v13_source_fields_persisted(async_client, dummy_jpeg, valid_meta):
    """v1.3 source fields are returned in GET /api/defects."""
    meta = copy.deepcopy(valid_meta)
    meta["localization_source"] = "yolov8n_detect_rknn"
    meta["label_source"] = "yolo_class_head"
    meta["observation_source"] = "template"
    meta["observation"] = "Test observation"

    await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(meta)},
    )

    resp = await async_client.get("/api/defects")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1

    item = items[0]
    assert item["localization_source"] == "yolov8n_detect_rknn"
    assert item["label_source"] == "yolo_class_head"
    assert item["observation_source"] == "template"
    assert item["observation"] == "Test observation"


async def test_v13_source_fields_none_when_omitted(async_client, dummy_jpeg, valid_meta):
    """v1.3 source fields are None when not provided."""
    await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(valid_meta)},
    )

    resp = await async_client.get("/api/defects")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1

    item = items[0]
    assert item.get("localization_source") is None
    assert item.get("label_source") is None
    assert item.get("observation_source") is None
