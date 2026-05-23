"""POST /api/edge/report — extended validation contract tests.

Covers cases not in the original test_post_report_validation.py:
  - All 15 MVTec AD categories accepted
  - Unknown field in meta rejected (extra="forbid")
  - Negative bbox rejected by Pydantic
  - Trace events round-trip through WS broadcast
  - Pipeline_ms missing stage rejected
"""

import copy
import json
from datetime import datetime, timezone

import pytest

MVTEC_15 = [
    "bottle", "cable", "capsule", "carpet", "grid", "hazelnut",
    "leather", "metal_nut", "pill", "screw", "tile", "toothbrush",
    "transistor", "wood", "zipper",
]


async def _post(client, jpeg, meta):
    return await client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", jpeg, "image/jpeg")},
        data={"meta": json.dumps(meta)},
    )


# ── All 15 categories accepted ───────────────────────────────────────────────


@pytest.mark.parametrize("category", MVTEC_15)
async def test_all_15_categories_accepted(async_client, dummy_jpeg, valid_meta, category):
    base = datetime.now(timezone.utc)
    valid_meta["category"] = category
    valid_meta["edge_ts"] = base.isoformat()
    resp = await _post(async_client, dummy_jpeg, valid_meta)
    assert resp.status_code == 200, f"category={category} rejected: {resp.text}"


# ── Extra field in meta rejected ─────────────────────────────────────────────


async def test_extra_field_rejected(async_client, dummy_jpeg, valid_meta):
    valid_meta["unknown_field"] = "should_be_rejected"
    resp = await _post(async_client, dummy_jpeg, valid_meta)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_extra_nested_field_in_vlm_metrics_rejected(async_client, dummy_jpeg, valid_meta):
    valid_meta["vlm_metrics"]["extra_key"] = 42
    resp = await _post(async_client, dummy_jpeg, valid_meta)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_extra_nested_field_in_bbox_rejected(async_client, dummy_jpeg, valid_meta):
    valid_meta["bboxes"] = [{"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2, "label": "bad"}]
    resp = await _post(async_client, dummy_jpeg, valid_meta)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


# ── Negative bbox rejected ───────────────────────────────────────────────────


async def test_negative_bbox_x_rejected(async_client, dummy_jpeg, valid_meta):
    valid_meta["bboxes"] = [{"x": -0.1, "y": 0.1, "w": 0.2, "h": 0.2}]
    resp = await _post(async_client, dummy_jpeg, valid_meta)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_negative_bbox_y_rejected(async_client, dummy_jpeg, valid_meta):
    valid_meta["bboxes"] = [{"x": 0.1, "y": -0.5, "w": 0.2, "h": 0.2}]
    resp = await _post(async_client, dummy_jpeg, valid_meta)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


# ── Pipeline_ms missing stage rejected ────────────────────────────────────────


async def test_pipeline_ms_missing_stage(async_client, dummy_jpeg, valid_meta):
    valid_meta["pipeline_ms"] = {"efficientad": 10.0, "fastsam": 40.0}  # missing qwen3vl
    resp = await _post(async_client, dummy_jpeg, valid_meta)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_pipeline_ms_extra_stage_rejected(async_client, dummy_jpeg, valid_meta):
    valid_meta["pipeline_ms"] = {
        "efficientad": 10.0, "fastsam": 40.0, "qwen3vl": 500.0, "extra": 99.0,
    }
    resp = await _post(async_client, dummy_jpeg, valid_meta)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


# ── Trace events round-trip through WS ───────────────────────────────────────


def test_trace_events_in_ws_broadcast(sync_client, dummy_jpeg, valid_meta):
    """Verify trace_events are present in the WS defect_created broadcast."""
    valid_meta["trace_events"] = [
        {"name": "EfficientAD_infer", "ts": 0.0, "dur": 12.3, "tid": "NPU.core0", "ph": "X", "cat": "infer"},
        {"name": "FastSAM_infer", "ts": 15.0, "dur": 78.9, "tid": "NPU.core1", "ph": "X", "cat": "infer"},
    ]
    valid_meta["edge_ts"] = "2026-05-23T10:00:00+00:00"

    with sync_client.websocket_connect("/ws/dashboard") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello"

        resp = sync_client.post(
            "/api/edge/report",
            files={"image": ("t.jpg", dummy_jpeg, "image/jpeg")},
            data={"meta": json.dumps(valid_meta)},
        )
        assert resp.status_code == 200

        msg = None
        for _ in range(10):
            msg = ws.receive_json()
            if msg.get("type") == "defect_created":
                break
        else:
            pytest.fail("Never received defect_created")

        data = msg["data"]
        assert "trace_events" in data
        assert data["trace_events"] is not None
        assert len(data["trace_events"]) == 2
        assert data["trace_events"][0]["name"] == "EfficientAD_infer"
        assert data["trace_events"][0]["dur"] == 12.3
