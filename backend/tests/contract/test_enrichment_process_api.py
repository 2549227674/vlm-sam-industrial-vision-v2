"""Phase 10.1 Step 2d: enrichment process API contract tests.

Tests for POST /api/enrich/{id}/process and POST /api/enrich/process-next.
Covers: success, no-pending, provider selection, error handling, YOLO protection.
"""

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest


def _passthrough_resolve(image_url: str) -> Path:
    """Mock resolver: return path without checking file existence."""
    return Path("/fake") / image_url.lstrip("/")


@pytest.fixture(autouse=True)
def _mock_image_resolver():
    """Patch image resolver so tests don't need real files on disk."""
    with patch(
        "backend.app.services.enrichment_worker.resolve_image_path",
        side_effect=_passthrough_resolve,
    ):
        yield


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _create_defect(async_client, dummy_jpeg, meta_override=None):
    """Post a defect and return its id."""
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
    if meta_override:
        meta.update(meta_override)
    resp = await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(meta)},
    )
    assert resp.status_code == 200, f"setup failed: {resp.status_code} {resp.text}"
    return resp.json()["id"]


async def _create_pending_enrichment(async_client, defect_id):
    """Create a pending enrichment job and return enrichment_id."""
    resp = await async_client.post(f"/api/defects/{defect_id}/enrich")
    assert resp.status_code == 202, f"enrich setup failed: {resp.status_code} {resp.text}"
    return resp.json()["enrichment_id"]


# ── A. Process by ID success with provider=template ─────────────────────────

async def test_process_by_id_success_template(async_client, dummy_jpeg):
    """POST /api/enrich/{id}/process?provider=template → complete."""
    defect_id = await _create_defect(async_client, dummy_jpeg)
    eid = await _create_pending_enrichment(async_client, defect_id)

    resp = await async_client.post(f"/api/enrich/{eid}/process?provider=template")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "complete"
    assert body["provider"] == "template"
    assert body["observation"] is not None
    assert len(body["observation"]) > 0
    assert body["severity_reason"] is not None
    assert len(body["severity_reason"]) > 0
    assert body["completed_at"] is not None


async def test_process_by_id_defect_denormalized(async_client, dummy_jpeg):
    """After successful process, GET /api/defects/{id} shows enriched fields."""
    defect_id = await _create_defect(async_client, dummy_jpeg)
    eid = await _create_pending_enrichment(async_client, defect_id)

    await async_client.post(f"/api/enrich/{eid}/process?provider=template")

    # GET defect should show denormalized observation
    resp = await async_client.get(f"/api/defects/{defect_id}")
    assert resp.status_code == 200
    defect = resp.json()
    assert defect["observation_source"] == "template"
    assert defect["observation"] is not None
    assert len(defect["observation"]) > 0


async def test_process_by_id_enrichment_shows_complete(async_client, dummy_jpeg):
    """After processing, GET enrichment shows complete status."""
    defect_id = await _create_defect(async_client, dummy_jpeg)
    eid = await _create_pending_enrichment(async_client, defect_id)

    await async_client.post(f"/api/enrich/{eid}/process?provider=template")

    resp = await async_client.get(f"/api/defects/{defect_id}/enrichment")
    assert resp.status_code == 200
    assert resp.json()["status"] == "complete"
    assert resp.json()["id"] == eid


# ── B. Process-next success with provider=template ──────────────────────────

async def test_process_next_success_template(async_client, dummy_jpeg):
    """POST /api/enrich/process-next?provider=template → processes oldest pending."""
    defect_id = await _create_defect(async_client, dummy_jpeg)
    eid = await _create_pending_enrichment(async_client, defect_id)

    resp = await async_client.post("/api/enrich/process-next?provider=template")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "complete"
    assert body["id"] == eid
    assert body["provider"] == "template"


# ── C. Process-next no pending ──────────────────────────────────────────────

async def test_process_next_no_pending_404(async_client):
    """POST /api/enrich/process-next when no pending → 404."""
    resp = await async_client.post("/api/enrich/process-next?provider=template")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "NO_PENDING_ENRICHMENT"


# ── D. Default provider disabled edge_vlm fails gracefully ──────────────────

async def test_default_provider_edge_vlm_disabled_fails(async_client, dummy_jpeg, monkeypatch):
    """With default env (edge_vlm disabled), process fails gracefully."""
    monkeypatch.setenv("ENRICHMENT_PROVIDER", "edge_vlm")
    monkeypatch.setenv("EDGE_VLM_MODE", "disabled")

    defect_id = await _create_defect(async_client, dummy_jpeg)
    eid = await _create_pending_enrichment(async_client, defect_id)

    # No provider= query param → uses env default (disabled edge_vlm)
    resp = await async_client.post(f"/api/enrich/{eid}/process")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert body["error_message"] is not None
    assert "disabled" in body["error_message"].lower()

    # Defect observation_source should NOT be changed to edge_vlm
    defect_resp = await async_client.get(f"/api/defects/{defect_id}")
    assert defect_resp.status_code == 200
    assert defect_resp.json()["observation_source"] != "edge_vlm"


# ── E. cloud_vlm rejected ───────────────────────────────────────────────────

async def test_cloud_vlm_rejected_501(async_client, dummy_jpeg):
    """provider=cloud_vlm → 501, no cloud call, pending job unchanged."""
    defect_id = await _create_defect(async_client, dummy_jpeg)
    eid = await _create_pending_enrichment(async_client, defect_id)

    resp = await async_client.post(f"/api/enrich/{eid}/process?provider=cloud_vlm")
    assert resp.status_code == 501
    assert resp.json()["error"]["code"] == "PROVIDER_NOT_IMPLEMENTED"

    # Pending job should remain pending (not attempted)
    get_resp = await async_client.get(f"/api/defects/{defect_id}/enrichment")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "pending"


# ── F. Unknown provider rejected ─────────────────────────────────────────────

async def test_unknown_provider_rejected_400(async_client, dummy_jpeg):
    """provider=magic → 400 INVALID_PROVIDER."""
    defect_id = await _create_defect(async_client, dummy_jpeg)
    eid = await _create_pending_enrichment(async_client, defect_id)

    resp = await async_client.post(f"/api/enrich/{eid}/process?provider=magic")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_PROVIDER"

    # Pending job should remain pending
    get_resp = await async_client.get(f"/api/defects/{defect_id}/enrichment")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "pending"


# ── G. Non-pending job process returns 409 ──────────────────────────────────

async def test_non_pending_returns_409(async_client, dummy_jpeg):
    """Processing an already-complete enrichment → 409 ENRICHMENT_NOT_PENDING."""
    defect_id = await _create_defect(async_client, dummy_jpeg)
    eid = await _create_pending_enrichment(async_client, defect_id)

    # Process once → complete
    resp1 = await async_client.post(f"/api/enrich/{eid}/process?provider=template")
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "complete"

    # Process again → 409
    resp2 = await async_client.post(f"/api/enrich/{eid}/process?provider=template")
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == "ENRICHMENT_NOT_PENDING"


# ── H. POST /api/edge/report does not auto-create enrichment ─────────────────

async def test_no_auto_enrichment_on_upload(async_client, dummy_jpeg):
    """POST /api/edge/report creates defect only, no enrichment row."""
    defect_id = await _create_defect(async_client, dummy_jpeg)

    resp = await async_client.get(f"/api/defects/{defect_id}/enrichment")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


# ── I. POST /api/defects/{id}/enrich creates pending only ────────────────────

async def test_enrich_creates_pending_no_process(async_client, dummy_jpeg):
    """POST /enrich creates pending job; defect observation_source unchanged."""
    defect_id = await _create_defect(async_client, dummy_jpeg)
    eid = await _create_pending_enrichment(async_client, defect_id)

    # enrichment is pending
    get_resp = await async_client.get(f"/api/defects/{defect_id}/enrichment")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "pending"

    # defect observation_source unchanged
    defect_resp = await async_client.get(f"/api/defects/{defect_id}")
    assert defect_resp.status_code == 200
    # Should be None or not "edge_vlm" — no provider call happened
    assert defect_resp.json()["observation_source"] is None


# ── J. YOLO-owned fields unchanged after template processing ─────────────────

async def test_yolo_fields_unchanged_after_template(async_client, dummy_jpeg):
    """YOLO-owned fields are protected after template processing."""
    defect_id = await _create_defect(async_client, dummy_jpeg)

    # Snapshot defect before enrichment
    before = (await async_client.get(f"/api/defects/{defect_id}")).json()

    eid = await _create_pending_enrichment(async_client, defect_id)
    await async_client.post(f"/api/enrich/{eid}/process?provider=template")

    after = (await async_client.get(f"/api/defects/{defect_id}")).json()

    assert after["category"] == before["category"]
    assert after["defect_type"] == before["defect_type"]
    assert after["confidence"] == before["confidence"]
    assert after["anomaly_score"] == before["anomaly_score"]
    assert after["bboxes"] == before["bboxes"]
    assert after["localization_source"] == before["localization_source"]
    assert after["label_source"] == before["label_source"]


# ── Nonexistent enrichment ID → 404 ─────────────────────────────────────────

async def test_process_nonexistent_enrichment_404(async_client):
    """Processing a nonexistent enrichment → 404."""
    resp = await async_client.post("/api/enrich/99999/process?provider=template")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


# ── Process-next with two pending picks oldest ───────────────────────────────

async def test_process_next_picks_oldest(async_client, dummy_jpeg):
    """process-next picks the oldest pending job."""
    d1 = await _create_defect(async_client, dummy_jpeg)
    d2 = await _create_defect(async_client, dummy_jpeg)
    e1 = await _create_pending_enrichment(async_client, d1)
    e2 = await _create_pending_enrichment(async_client, d2)

    resp = await async_client.post("/api/enrich/process-next?provider=template")
    assert resp.status_code == 200
    assert resp.json()["id"] == e1  # oldest first
    assert resp.json()["status"] == "complete"

    # Second call picks the next one
    resp2 = await async_client.post("/api/enrich/process-next?provider=template")
    assert resp2.status_code == 200
    assert resp2.json()["id"] == e2
