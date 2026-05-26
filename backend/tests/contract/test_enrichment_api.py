"""Phase 10.1 Step 1: enrichment job API contract tests.

Tests:
  - POST /api/defects/{id}/enrich creates pending job (202)
  - 404 for missing defect
  - 400 for empty bboxes
  - 400 for confidence=0 / fallback placeholder
  - 409 for duplicate pending/running job
  - GET /api/defects/{id}/enrichment returns latest
  - GET /api/defects/{id}/enrichment 404 when none exist
"""

import copy
import json
from datetime import datetime, timezone


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


# ── Tests ────────────────────────────────────────────────────────────────────

async def test_enrich_creates_pending_job(async_client, dummy_jpeg):
    """POST /api/defects/{id}/enrich returns 202 with pending status."""
    defect_id = await _create_defect(async_client, dummy_jpeg)
    resp = await async_client.post(f"/api/defects/{defect_id}/enrich")
    assert resp.status_code == 202
    body = resp.json()
    assert body["defect_id"] == defect_id
    assert body["status"] == "pending"
    assert "enrichment_id" in body


async def test_enrich_nonexistent_defect_404(async_client):
    """POST /api/defects/99999/enrich returns 404."""
    resp = await async_client.post("/api/defects/99999/enrich")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


async def test_enrich_empty_bboxes_400(async_client, dummy_jpeg):
    """Defect with empty bboxes cannot be enriched."""
    defect_id = await _create_defect(
        async_client, dummy_jpeg,
        meta_override={"bboxes": []},
    )
    resp = await async_client.post(f"/api/defects/{defect_id}/enrich")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "EMPTY_BBOXES"


async def test_enrich_zero_confidence_400(async_client, dummy_jpeg):
    """Defect with confidence=0 cannot be enriched."""
    defect_id = await _create_defect(
        async_client, dummy_jpeg,
        meta_override={
            "confidence": 0,
            "defect_type": "anomaly",
            "bboxes": [{"x": 0.3, "y": 0.3, "w": 0.4, "h": 0.4}],
        },
    )
    resp = await async_client.post(f"/api/defects/{defect_id}/enrich")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] in ("ZERO_CONFIDENCE", "FALLBACK_PLACEHOLDER")


async def test_enrich_fallback_placeholder_400(async_client, dummy_jpeg):
    """Fallback placeholder defect (anomaly + conf=0 + center box) cannot be enriched."""
    defect_id = await _create_defect(
        async_client, dummy_jpeg,
        meta_override={
            "confidence": 0,
            "defect_type": "anomaly",
            "bboxes": [{"x": 0.3, "y": 0.3, "w": 0.4, "h": 0.4}],
        },
    )
    resp = await async_client.post(f"/api/defects/{defect_id}/enrich")
    assert resp.status_code == 400


async def test_enrich_duplicate_pending_409(async_client, dummy_jpeg):
    """Second enrich call on same defect returns 409."""
    defect_id = await _create_defect(async_client, dummy_jpeg)
    resp1 = await async_client.post(f"/api/defects/{defect_id}/enrich")
    assert resp1.status_code == 202

    resp2 = await async_client.post(f"/api/defects/{defect_id}/enrich")
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == "DUPLICATE_ENRICHMENT"


async def test_get_enrichment_returns_latest(async_client, dummy_jpeg):
    """GET /api/defects/{id}/enrichment returns the enrichment record."""
    defect_id = await _create_defect(async_client, dummy_jpeg)
    post_resp = await async_client.post(f"/api/defects/{defect_id}/enrich")
    assert post_resp.status_code == 202
    enrichment_id = post_resp.json()["enrichment_id"]

    get_resp = await async_client.get(f"/api/defects/{defect_id}/enrichment")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["id"] == enrichment_id
    assert body["defect_id"] == defect_id
    assert body["provider"] == "edge_vlm"
    assert body["status"] == "pending"
    assert body["prompt_version"] == "phase10_1_obs_v1"


async def test_get_enrichment_not_found_404(async_client):
    """GET /api/defects/99999/enrichment returns 404 when no enrichment exists."""
    resp = await async_client.get("/api/defects/99999/enrichment")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


async def test_existing_contract_tests_still_pass(async_client, dummy_jpeg, valid_meta):
    """Sanity: existing v1.3 POST + GET still works after enrichment model added."""
    resp = await async_client.post(
        "/api/edge/report",
        files={"image": ("test.jpg", dummy_jpeg, "image/jpeg")},
        data={"meta": json.dumps(valid_meta)},
    )
    assert resp.status_code == 200

    resp = await async_client.get("/api/defects")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
