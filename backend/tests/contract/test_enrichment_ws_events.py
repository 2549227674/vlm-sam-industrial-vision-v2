"""Enrichment WebSocket event contract tests.

Validates:
  - Event payload schema for all 5 enrichment statuses
  - Forbidden fields are never present in event payloads
  - Error message sanitization
  - Auto-enqueue emits pending event without calling provider
  - Manual enrichment trigger emits pending event
"""

import json
from datetime import datetime, timezone

import pytest

from backend.app.services.enrichment_ws_events import (
    build_enrichment_event,
    sanitize_error_message,
)


# ── Event payload schema ─────────────────────────────────────────────────────


class TestBuildEnrichmentEvent:
    """Validate event payload structure for all statuses."""

    @pytest.mark.parametrize("status", ["pending", "running", "complete", "rejected", "failed"])
    def test_event_has_required_fields(self, status):
        event = build_enrichment_event(
            defect_id=1,
            enrichment_id=10,
            status=status,
            provider="edge_vlm",
        )
        assert event["type"] == "defect_enrichment_updated"
        assert event["defect_id"] == 1
        assert event["enrichment_id"] == 10
        assert event["status"] == status
        assert event["provider"] == "edge_vlm"
        assert "ts" in event
        assert "updated_fields" in event
        assert "error_message" in event

    def test_complete_has_updated_fields(self):
        event = build_enrichment_event(
            defect_id=1,
            enrichment_id=10,
            status="complete",
            provider="edge_vlm",
            observation_source="edge_vlm",
        )
        assert "observation" in event["updated_fields"]
        assert "severity_reason" in event["updated_fields"]
        assert "observation_source" in event["updated_fields"]
        assert event["observation_source"] == "edge_vlm"

    def test_pending_has_empty_updated_fields(self):
        event = build_enrichment_event(
            defect_id=1,
            enrichment_id=10,
            status="pending",
            provider="template",
        )
        assert event["updated_fields"] == []

    def test_running_has_empty_updated_fields(self):
        event = build_enrichment_event(
            defect_id=1,
            enrichment_id=10,
            status="running",
            provider="edge_vlm",
        )
        assert event["updated_fields"] == []

    def test_ts_is_iso8601(self):
        event = build_enrichment_event(
            defect_id=1,
            enrichment_id=10,
            status="pending",
            provider="edge_vlm",
        )
        # Should parse without error
        datetime.fromisoformat(event["ts"])

    def test_event_is_json_serializable(self):
        event = build_enrichment_event(
            defect_id=1,
            enrichment_id=10,
            status="complete",
            provider="edge_vlm",
            observation_source="edge_vlm",
            error_message=None,
        )
        # Should not raise
        json.dumps(event)


# ── Forbidden field exclusion ─────────────────────────────────────────────────


FORBIDDEN_PAYLOAD_KEYS = frozenset({
    "bbox", "bboxes", "mask", "category", "defect_type",
    "confidence", "anomaly_score", "geometry_correction",
    "localization_source", "label_source",
})


class TestForbiddenFields:
    """Event payloads must never contain forbidden keys."""

    @pytest.mark.parametrize("status", ["pending", "running", "complete", "rejected", "failed"])
    def test_no_forbidden_keys_in_payload(self, status):
        event = build_enrichment_event(
            defect_id=1,
            enrichment_id=10,
            status=status,
            provider="edge_vlm",
            observation_source="edge_vlm",
            error_message="test error",
        )
        present = FORBIDDEN_PAYLOAD_KEYS & event.keys()
        assert not present, f"Forbidden keys present: {sorted(present)}"

    def test_no_raw_command_in_error(self):
        event = build_enrichment_event(
            defect_id=1,
            enrichment_id=10,
            status="failed",
            provider="edge_vlm",
            error_message="EDGE_VLM_COMMAND=/usr/bin/vlm_runner --model /data/models/foo.rkllm",
        )
        assert "/usr/bin" not in (event["error_message"] or "")
        assert "EDGE_VLM_COMMAND" not in (event["error_message"] or "")

    def test_no_ip_in_error(self):
        event = build_enrichment_event(
            defect_id=1,
            enrichment_id=10,
            status="failed",
            provider="edge_vlm",
            error_message="Connection to 192.168.1.100:8080 failed",
        )
        assert "192.168.1.100" not in (event["error_message"] or "")

    def test_no_path_in_error(self):
        event = build_enrichment_event(
            defect_id=1,
            enrichment_id=10,
            status="failed",
            provider="edge_vlm",
            error_message="FileNotFoundError: /home/ubuntu/models/qwen3-vl-2b.rkllm not found",
        )
        assert "/home/ubuntu" not in (event["error_message"] or "")

    def test_no_stack_trace_in_error(self):
        event = build_enrichment_event(
            defect_id=1,
            enrichment_id=10,
            status="failed",
            provider="edge_vlm",
            error_message='File "/home/user/app.py", line 42, in process\nRuntimeError: boom',
        )
        assert "/home/user" not in (event["error_message"] or "")


# ── Error sanitization ───────────────────────────────────────────────────────


class TestSanitizeErrorMessage:
    """Error messages are sanitized for frontend display."""

    def test_none_returns_none(self):
        assert sanitize_error_message(None) is None

    def test_empty_returns_none(self):
        assert sanitize_error_message("") is None

    def test_whitespace_returns_none(self):
        assert sanitize_error_message("   ") is None

    def test_clean_message_passes_through(self):
        result = sanitize_error_message("Provider returned invalid JSON")
        assert result == "Provider returned invalid JSON"

    def test_filesystem_path_redacted(self):
        result = sanitize_error_message("File /home/ubuntu/models/foo.rkllm not found")
        assert "/home/ubuntu" not in result
        assert "[redacted]" in result

    def test_ip_redacted(self):
        result = sanitize_error_message("Cannot connect to 10.0.0.1:8080")
        assert "10.0.0.1" not in result

    def test_token_redacted(self):
        result = sanitize_error_message("token=sk_abc123def456 expired")
        assert "sk_abc123def456" not in result

    def test_sshpass_redacted(self):
        result = sanitize_error_message("sshpass -p MySecretPass ssh user@host")
        assert "MySecretPass" not in result
        assert "sshpass" not in result

    def test_edge_vlm_command_redacted(self):
        result = sanitize_error_message("EDGE_VLM_COMMAND=/usr/local/bin/vlm --model /data/x.rkllm")
        assert "/usr/local/bin" not in result

    def test_truncated_to_200_chars(self):
        long_msg = "Error: " + "x" * 500
        result = sanitize_error_message(long_msg)
        assert len(result) <= 210  # 200 + "..." + some redaction overhead

    def test_stack_trace_redacted(self):
        result = sanitize_error_message(
            'Traceback:\n  File "/app/main.py", line 42\nRuntimeError: boom'
        )
        assert "/app/main.py" not in result


# ── Integration: WS broadcast contract ───────────────────────────────────────


class TestEnrichmentWsBroadcast:
    """Test enrichment WS events through the full backend stack."""

    def test_manual_trigger_emits_pending_event(self, sync_client, dummy_jpeg, valid_meta):
        """POST /defects/{id}/enrich should emit a pending enrichment event via WS."""
        # Create a defect first
        meta = {
            **valid_meta,
            "edge_ts": "2026-05-27T10:00:00+00:00",
        }
        resp = sync_client.post(
            "/api/edge/report",
            files={"image": ("t.jpg", dummy_jpeg, "image/jpeg")},
            data={"meta": json.dumps(meta)},
        )
        assert resp.status_code == 200
        defect_id = resp.json()["id"]

        # Connect WS
        with sync_client.websocket_connect("/ws/dashboard") as ws:
            # Skip hello
            hello = ws.receive_json()
            assert hello["type"] == "hello"

            # Trigger manual enrichment
            enrich_resp = sync_client.post(f"/api/defects/{defect_id}/enrich")
            assert enrich_resp.status_code == 202

            # Collect WS messages until we find the enrichment event
            enrichment_event = None
            for _ in range(15):
                msg = ws.receive_json()
                if msg.get("type") == "defect_enrichment_updated":
                    enrichment_event = msg
                    break
                if msg.get("type") in ("defect_created", "metrics_tick", "ping"):
                    continue  # skip other broadcasts

            assert enrichment_event is not None, "Never received defect_enrichment_updated"
            assert enrichment_event["status"] == "pending"
            assert enrichment_event["defect_id"] == defect_id
            assert enrichment_event["provider"] == "edge_vlm"
            assert enrichment_event["type"] == "defect_enrichment_updated"

    def test_process_emits_running_and_terminal_events(self, sync_client, dummy_jpeg, valid_meta):
        """POST /enrich/{id}/process with template provider emits running + complete/rejected."""
        # Create a defect
        meta = {
            **valid_meta,
            "edge_ts": "2026-05-27T10:01:00+00:00",
        }
        resp = sync_client.post(
            "/api/edge/report",
            files={"image": ("t.jpg", dummy_jpeg, "image/jpeg")},
            data={"meta": json.dumps(meta)},
        )
        assert resp.status_code == 200
        defect_id = resp.json()["id"]

        # Create enrichment
        enrich_resp = sync_client.post(f"/api/defects/{defect_id}/enrich")
        assert enrich_resp.status_code == 202
        enrichment_id = enrich_resp.json()["enrichment_id"]

        # Connect WS and process
        with sync_client.websocket_connect("/ws/dashboard") as ws:
            hello = ws.receive_json()
            assert hello["type"] == "hello"

            # Process with template provider
            process_resp = sync_client.post(
                f"/api/enrich/{enrichment_id}/process?provider=template",
            )
            assert process_resp.status_code == 200

            # Collect enrichment events
            events = []
            for _ in range(20):
                msg = ws.receive_json()
                if msg.get("type") == "defect_enrichment_updated":
                    events.append(msg)
                    # After getting at least 2 events (running + terminal), stop
                    if len(events) >= 2:
                        break
                if msg.get("type") in ("metrics_tick", "ping"):
                    continue

            # Should have at least running + terminal (complete or rejected)
            statuses = [e["status"] for e in events]
            assert "running" in statuses, f"Expected 'running' event, got {statuses}"
            assert any(s in statuses for s in ("complete", "rejected")), \
                f"Expected terminal event, got {statuses}"

            # Terminal event must not contain forbidden keys
            for event in events:
                for forbidden in ("bbox", "bboxes", "category", "defect_type", "confidence", "anomaly_score"):
                    assert forbidden not in event, f"Forbidden key '{forbidden}' in event payload"

    def test_event_does_not_mutate_defect_fields(self, sync_client, dummy_jpeg, valid_meta):
        """Enrichment event payload must not contain defect mutation fields."""
        meta = {
            **valid_meta,
            "edge_ts": "2026-05-27T10:02:00+00:00",
        }
        resp = sync_client.post(
            "/api/edge/report",
            files={"image": ("t.jpg", dummy_jpeg, "image/jpeg")},
            data={"meta": json.dumps(meta)},
        )
        assert resp.status_code == 200
        defect_id = resp.json()["id"]

        enrich_resp = sync_client.post(f"/api/defects/{defect_id}/enrich")
        assert enrich_resp.status_code == 202
        enrichment_id = enrich_resp.json()["enrichment_id"]

        with sync_client.websocket_connect("/ws/dashboard") as ws:
            ws.receive_json()  # hello

            sync_client.post(f"/api/enrich/{enrichment_id}/process?provider=template")

            events = []
            for _ in range(20):
                msg = ws.receive_json()
                if msg.get("type") == "defect_enrichment_updated":
                    events.append(msg)
                    if len(events) >= 2:
                        break
                if msg.get("type") in ("metrics_tick", "ping"):
                    continue

            for event in events:
                # These mutation keys must never appear in event payload
                for key in ("bbox", "bboxes", "category", "defect_type",
                            "confidence", "anomaly_score", "localization_source",
                            "label_source"):
                    assert key not in event

                # Raw command / credentials must not appear
                error_msg = event.get("error_message") or ""
                assert "EDGE_VLM_COMMAND" not in error_msg
                assert "sshpass" not in error_msg
                assert "password" not in error_msg.lower() or "[redacted]" in error_msg


class TestEdgeReportNonBlocking:
    """POST /api/edge/report must not call provider."""

    def test_report_does_not_call_provider(self, sync_client, dummy_jpeg, valid_meta):
        """Report endpoint returns immediately without VLM processing."""
        import time

        meta = {
            **valid_meta,
            "edge_ts": "2026-05-27T10:03:00+00:00",
        }
        start = time.monotonic()
        resp = sync_client.post(
            "/api/edge/report",
            files={"image": ("t.jpg", dummy_jpeg, "image/jpeg")},
            data={"meta": json.dumps(meta)},
        )
        elapsed = time.monotonic() - start

        assert resp.status_code == 200
        # If provider were called synchronously, this would take 10+ seconds
        assert elapsed < 2.0, f"Report took {elapsed:.1f}s — provider may be called synchronously"
