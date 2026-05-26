"""Phase 10.1: Hallucination guard unit tests.

Tests for backend/app/services/enrichment_guard.py — strict validation of VLM output.
"""

import json

import pytest

from backend.app.services.enrichment_guard import (
    EnrichmentValidationError,
    validate_vlm_output,
)


# ── Valid inputs ─────────────────────────────────────────────────────────────

def test_valid_dict_accepted():
    """Valid dict with all three keys is accepted."""
    result = validate_vlm_output(
        {"observation": "test obs", "severity_reason": "test reason", "accepted_box_ids": [0]},
        input_box_ids=[0, 1],
    )
    assert result["observation"] == "test obs"
    assert result["severity_reason"] == "test reason"
    assert result["accepted_box_ids"] == [0]


def test_valid_json_string_accepted():
    """Valid JSON string is parsed and accepted."""
    raw = json.dumps({"observation": "obs", "severity_reason": "reason", "accepted_box_ids": [0]})
    result = validate_vlm_output(raw, input_box_ids=[0])
    assert result["observation"] == "obs"


def test_missing_accepted_box_ids_defaults_to_all():
    """When accepted_box_ids is absent, defaults to all input box IDs."""
    result = validate_vlm_output(
        {"observation": "obs", "severity_reason": "reason"},
        input_box_ids=[0, 1, 2],
    )
    assert result["accepted_box_ids"] == [0, 1, 2]


def test_missing_accepted_box_ids_no_input_defaults_empty():
    """When accepted_box_ids absent and no input_box_ids, defaults to empty."""
    result = validate_vlm_output(
        {"observation": "obs", "severity_reason": "reason"},
        input_box_ids=None,
    )
    assert result["accepted_box_ids"] == []


def test_whitespace_stripped():
    """Leading/trailing whitespace in strings is stripped."""
    result = validate_vlm_output(
        {"observation": "  obs  ", "severity_reason": "  reason  ", "accepted_box_ids": []},
        input_box_ids=[],
    )
    assert result["observation"] == "obs"
    assert result["severity_reason"] == "reason"


# ── Invalid JSON ─────────────────────────────────────────────────────────────

def test_invalid_json_rejected():
    """Non-JSON string is rejected."""
    with pytest.raises(EnrichmentValidationError, match="Invalid JSON"):
        validate_vlm_output("not json at all", input_box_ids=[])


def test_markdown_fenced_json_rejected():
    """Markdown fenced JSON is rejected."""
    raw = '```json\n{"observation":"obs","severity_reason":"reason"}\n```'
    with pytest.raises(EnrichmentValidationError, match="markdown fence"):
        validate_vlm_output(raw, input_box_ids=[])


def test_prose_wrapped_json_rejected():
    """Prose wrapper before JSON is rejected (not valid JSON)."""
    raw = 'Here is the output:\n{"observation":"obs","severity_reason":"reason"}'
    with pytest.raises(EnrichmentValidationError):
        validate_vlm_output(raw, input_box_ids=[])


def test_non_dict_json_rejected():
    """JSON array or string at top level is rejected."""
    with pytest.raises(EnrichmentValidationError, match="JSON object"):
        validate_vlm_output('["observation", "reason"]', input_box_ids=[])


def test_non_str_or_dict_input_rejected():
    """Non-str, non-dict input is rejected."""
    with pytest.raises(EnrichmentValidationError, match="Expected str or dict"):
        validate_vlm_output(42, input_box_ids=[])


# ── Forbidden keys ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("key", [
    "bbox", "bboxes", "mask", "category", "defect_type",
    "confidence", "anomaly_score", "geometry_correction",
    "localization_source", "label_source",
])
def test_forbidden_key_rejected(key):
    """Any forbidden key in output is rejected."""
    data = {"observation": "obs", "severity_reason": "reason", key: "value"}
    with pytest.raises(EnrichmentValidationError, match="Forbidden keys"):
        validate_vlm_output(data, input_box_ids=[])


# ── Extra keys ───────────────────────────────────────────────────────────────

def test_extra_keys_rejected():
    """Unknown extra keys not in allowed set are rejected."""
    data = {"observation": "obs", "severity_reason": "reason", "unknown_field": "val"}
    with pytest.raises(EnrichmentValidationError, match="Extra keys"):
        validate_vlm_output(data, input_box_ids=[])


# ── observation validation ───────────────────────────────────────────────────

def test_empty_observation_rejected():
    """Empty observation string is rejected."""
    data = {"observation": "", "severity_reason": "reason"}
    with pytest.raises(EnrichmentValidationError, match="observation"):
        validate_vlm_output(data, input_box_ids=[])


def test_whitespace_only_observation_rejected():
    """Whitespace-only observation is rejected."""
    data = {"observation": "   ", "severity_reason": "reason"}
    with pytest.raises(EnrichmentValidationError, match="observation"):
        validate_vlm_output(data, input_box_ids=[])


def test_missing_observation_rejected():
    """Missing observation key is rejected."""
    data = {"severity_reason": "reason"}
    with pytest.raises(EnrichmentValidationError, match="observation"):
        validate_vlm_output(data, input_box_ids=[])


def test_overlong_observation_rejected():
    """observation > 1024 chars is rejected."""
    data = {"observation": "x" * 1025, "severity_reason": "reason"}
    with pytest.raises(EnrichmentValidationError, match="exceeds 1024"):
        validate_vlm_output(data, input_box_ids=[])


def test_observation_at_1024_accepted():
    """observation exactly 1024 chars is accepted."""
    data = {"observation": "x" * 1024, "severity_reason": "reason"}
    result = validate_vlm_output(data, input_box_ids=[])
    assert len(result["observation"]) == 1024


# ── severity_reason validation ───────────────────────────────────────────────

def test_empty_severity_reason_rejected():
    """Empty severity_reason is rejected."""
    data = {"observation": "obs", "severity_reason": ""}
    with pytest.raises(EnrichmentValidationError, match="severity_reason"):
        validate_vlm_output(data, input_box_ids=[])


def test_missing_severity_reason_rejected():
    """Missing severity_reason key is rejected."""
    data = {"observation": "obs"}
    with pytest.raises(EnrichmentValidationError, match="severity_reason"):
        validate_vlm_output(data, input_box_ids=[])


def test_overlong_severity_reason_rejected():
    """severity_reason > 512 chars is rejected."""
    data = {"observation": "obs", "severity_reason": "x" * 513}
    with pytest.raises(EnrichmentValidationError, match="exceeds 512"):
        validate_vlm_output(data, input_box_ids=[])


def test_severity_reason_at_512_accepted():
    """severity_reason exactly 512 chars is accepted."""
    data = {"observation": "obs", "severity_reason": "x" * 512}
    result = validate_vlm_output(data, input_box_ids=[])
    assert len(result["severity_reason"]) == 512


# ── accepted_box_ids validation ──────────────────────────────────────────────

def test_accepted_box_ids_non_list_rejected():
    """accepted_box_ids that is not a list is rejected."""
    data = {"observation": "obs", "severity_reason": "reason", "accepted_box_ids": "0"}
    with pytest.raises(EnrichmentValidationError, match="must be a list"):
        validate_vlm_output(data, input_box_ids=[0])


def test_accepted_box_ids_non_int_rejected():
    """accepted_box_ids containing non-int is rejected."""
    data = {"observation": "obs", "severity_reason": "reason", "accepted_box_ids": ["a"]}
    with pytest.raises(EnrichmentValidationError, match="not an int"):
        validate_vlm_output(data, input_box_ids=[0, 1])


def test_accepted_box_ids_outside_range_rejected():
    """accepted_box_ids with IDs not in input is rejected."""
    data = {"observation": "obs", "severity_reason": "reason", "accepted_box_ids": [0, 5]}
    with pytest.raises(EnrichmentValidationError, match="not in input"):
        validate_vlm_output(data, input_box_ids=[0, 1, 2])


def test_accepted_box_ids_empty_list_accepted():
    """Empty accepted_box_ids list is valid."""
    data = {"observation": "obs", "severity_reason": "reason", "accepted_box_ids": []}
    result = validate_vlm_output(data, input_box_ids=[0, 1])
    assert result["accepted_box_ids"] == []


def test_accepted_box_ids_subset_accepted():
    """Subset of input box IDs is accepted."""
    data = {"observation": "obs", "severity_reason": "reason", "accepted_box_ids": [1]}
    result = validate_vlm_output(data, input_box_ids=[0, 1, 2])
    assert result["accepted_box_ids"] == [1]
