"""Phase 10.1b: /api/edge/report auto-enqueue integration tests.

Covers:
  - Default env flags false -> POST /api/edge/report creates defect only, no enrichment row
  - ENRICHMENT_ENABLED=true and ENRICHMENT_AUTO_ENQUEUE=false -> no enrichment row
  - ENRICHMENT_ENABLED=true and ENRICHMENT_AUTO_ENQUEUE=true -> enrichment row created pending
  - Response payload remains DefectCreatedResponse (no enrichment fields)
  - No provider call during edge/report
  - Upload path does not process job; enrichment remains pending after report
"""

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from backend.app.models.enrichment import DefectEnrichment


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_meta(**overrides):
    meta = {
        "line_id": "L1",
        "category": "metal_nut",
        "defect_type": "scratch",
        "severity": "high",
        "confidence": 0.95,
        "anomaly_score": 12.5,
        "bboxes": [{"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}],
        "description": "test scratch",
        "variant": "ort_2B",
        "edge_ts": datetime.now(timezone.utc).isoformat(),
        "pipeline_ms": {"efficientad": 12.0, "localizer": 25.0, "upload": 5.0},
        "schema_version": "v1",
    }
    meta.update(overrides)
    return meta


async def _post_report(async_client, dummy_jpeg, meta_override=None):
    meta = _make_meta(**(meta_override or {}))
    return await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(meta)},
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

async def test_default_flags_no_enrichment(async_client, dummy_jpeg, monkeypatch):
    """With defaults (both flags off), /api/edge/report creates no enrichment row."""
    monkeypatch.delenv("ENRICHMENT_ENABLED", raising=False)
    monkeypatch.delenv("ENRICHMENT_AUTO_ENQUEUE", raising=False)

    resp = await _post_report(async_client, dummy_jpeg)
    assert resp.status_code == 200
    defect_id = resp.json()["id"]

    # No enrichment row should exist
    from backend.app.db import get_db

    # Query through the app's DB override
    # We can check via the API endpoint instead
    enrich_resp = await async_client.get(f"/api/defects/{defect_id}/enrichment")
    assert enrich_resp.status_code == 404


async def test_enabled_but_auto_enqueue_off(async_client, dummy_jpeg, monkeypatch):
    """enabled=true but auto_enqueue=false -> no enrichment row."""
    monkeypatch.setenv("ENRICHMENT_ENABLED", "true")
    monkeypatch.setenv("ENRICHMENT_AUTO_ENQUEUE", "false")

    resp = await _post_report(async_client, dummy_jpeg)
    assert resp.status_code == 200
    defect_id = resp.json()["id"]

    enrich_resp = await async_client.get(f"/api/defects/{defect_id}/enrichment")
    assert enrich_resp.status_code == 404


async def test_both_enabled_creates_pending_enrichment(async_client, dummy_jpeg, monkeypatch):
    """enabled=true and auto_enqueue=true -> enrichment row created as pending."""
    monkeypatch.setenv("ENRICHMENT_ENABLED", "true")
    monkeypatch.setenv("ENRICHMENT_AUTO_ENQUEUE", "true")

    resp = await _post_report(async_client, dummy_jpeg)
    assert resp.status_code == 200
    defect_id = resp.json()["id"]

    # Enrichment should exist and be pending
    enrich_resp = await async_client.get(f"/api/defects/{defect_id}/enrichment")
    assert enrich_resp.status_code == 200
    enrich_data = enrich_resp.json()
    assert enrich_data["defect_id"] == defect_id
    assert enrich_data["status"] == "pending"
    assert enrich_data["provider"] == "edge_vlm"
    assert enrich_data["prompt_version"] == "phase10_1_obs_v1"


async def test_response_schema_unchanged(async_client, dummy_jpeg, monkeypatch):
    """Response must remain DefectCreatedResponse — no enrichment fields added."""
    monkeypatch.setenv("ENRICHMENT_ENABLED", "true")
    monkeypatch.setenv("ENRICHMENT_AUTO_ENQUEUE", "true")

    resp = await _post_report(async_client, dummy_jpeg)
    assert resp.status_code == 200
    body = resp.json()

    # DefectCreatedResponse has exactly: id, image_url, server_ts
    assert set(body.keys()) == {"id", "image_url", "server_ts"}


async def test_enrichment_remains_pending(async_client, dummy_jpeg, monkeypatch):
    """Auto-enqueue creates pending job only — does NOT process it."""
    monkeypatch.setenv("ENRICHMENT_ENABLED", "true")
    monkeypatch.setenv("ENRICHMENT_AUTO_ENQUEUE", "true")

    resp = await _post_report(async_client, dummy_jpeg)
    assert resp.status_code == 200
    defect_id = resp.json()["id"]

    enrich_resp = await async_client.get(f"/api/defects/{defect_id}/enrichment")
    assert enrich_resp.status_code == 200
    assert enrich_resp.json()["status"] == "pending"
    assert enrich_resp.json()["completed_at"] is None


async def test_no_provider_call_during_report(async_client, dummy_jpeg, monkeypatch):
    """Provider factory should not be invoked during /api/edge/report."""
    monkeypatch.setenv("ENRICHMENT_ENABLED", "true")
    monkeypatch.setenv("ENRICHMENT_AUTO_ENQUEUE", "true")

    call_log = []

    def fake_get_provider(*args, **kwargs):
        call_log.append("get_provider_called")
        raise AssertionError("Provider should not be called during auto-enqueue")

    monkeypatch.setattr(
        "backend.app.services.provider_factory.get_provider_from_env",
        fake_get_provider,
    )

    resp = await _post_report(async_client, dummy_jpeg)
    assert resp.status_code == 200
    assert len(call_log) == 0


async def test_empty_bboxes_no_auto_enqueue(async_client, dummy_jpeg, monkeypatch):
    """Defect with empty bboxes should not get auto-enqueued."""
    monkeypatch.setenv("ENRICHMENT_ENABLED", "true")
    monkeypatch.setenv("ENRICHMENT_AUTO_ENQUEUE", "true")

    resp = await _post_report(async_client, dummy_jpeg, meta_override={"bboxes": []})
    assert resp.status_code == 200
    defect_id = resp.json()["id"]

    enrich_resp = await async_client.get(f"/api/defects/{defect_id}/enrichment")
    assert enrich_resp.status_code == 404


async def test_zero_confidence_no_auto_enqueue(async_client, dummy_jpeg, monkeypatch):
    """Defect with confidence=0 should not get auto-enqueued."""
    monkeypatch.setenv("ENRICHMENT_ENABLED", "true")
    monkeypatch.setenv("ENRICHMENT_AUTO_ENQUEUE", "true")

    resp = await _post_report(async_client, dummy_jpeg, meta_override={"confidence": 0.0})
    assert resp.status_code == 200
    defect_id = resp.json()["id"]

    enrich_resp = await async_client.get(f"/api/defects/{defect_id}/enrichment")
    assert enrich_resp.status_code == 404


async def test_manual_enrich_after_auto_enqueue(async_client, dummy_jpeg, monkeypatch):
    """Manual enrich should fail with 409 if auto-enqueue already created a pending job."""
    monkeypatch.setenv("ENRICHMENT_ENABLED", "true")
    monkeypatch.setenv("ENRICHMENT_AUTO_ENQUEUE", "true")

    resp = await _post_report(async_client, dummy_jpeg)
    assert resp.status_code == 200
    defect_id = resp.json()["id"]

    # Manual enrich should 409 because auto-enqueue already created a pending row
    manual_resp = await async_client.post(f"/api/defects/{defect_id}/enrich")
    assert manual_resp.status_code == 409
    assert manual_resp.json()["error"]["code"] == "DUPLICATE_ENRICHMENT"
