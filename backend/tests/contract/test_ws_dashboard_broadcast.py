"""WebSocket /ws/dashboard — hello + broadcast contract tests.

Uses sync TestClient (lifespan IS triggered → ws_manager initialized).
"""

import json

import pytest


def test_ws_hello_and_broadcast(sync_client, dummy_jpeg, valid_meta):
    with sync_client.websocket_connect("/ws/dashboard") as ws:
        # 1. hello message
        hello = ws.receive_json()
        assert hello["type"] == "hello"
        assert "ws_id" in hello
        assert "server_ts" in hello

        # 2. POST triggers broadcast
        meta = {
            "line_id": "L1",
            "category": "metal_nut",
            "defect_type": "scratch",
            "severity": "high",
            "confidence": 0.95,
            "anomaly_score": 12.5,
            "bboxes": [{"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}],
            "description": "ws test",
            "variant": "2B_base",
            "edge_ts": "2026-05-09T08:00:00+00:00",
            "pipeline_ms": {"efficientad": 12.0, "fastsam": 45.0, "qwen3vl": 850.0},
            "vlm_metrics": {
                "ttft_ms": 600.0,
                "decode_tps": 15.0,
                "prompt_tokens": 800,
                "output_tokens": 50,
                "rss_mb": 2500.0,
                "json_parse_ok": True,
            },
            "schema_version": "v1",
        }
        resp = sync_client.post(
            "/api/edge/report",
            files={"image": ("t.jpg", dummy_jpeg, "image/jpeg")},
            data={"meta": json.dumps(meta)},
        )
        assert resp.status_code == 200

        # 3. consume until defect_created (skip metrics_tick / ping)
        msg = None
        for _ in range(10):
            msg = ws.receive_json()
            if msg.get("type") == "defect_created":
                break
        else:
            pytest.fail("Never received defect_created within 10 messages")

        # 4. validate defect_created payload
        assert msg["type"] == "defect_created"
        data = msg["data"]
        assert data["category"] == "metal_nut"
        assert data["defect_type"] == "scratch"
        assert "id" in data
        assert "image_url" in data
        assert "server_ts" in data
