# Phase 10.1: Hallucination guard — strict validation of VLM provider output.
#
# Rejects any output containing forbidden keys (bbox, category, etc.).
# Never writes forbidden fields to defects table.

from __future__ import annotations

import json
from typing import Any


class EnrichmentValidationError(Exception):
    """Raised when VLM output fails hallucination guard validation."""
    pass


ALLOWED_KEYS = frozenset({"observation", "severity_reason", "accepted_box_ids"})

FORBIDDEN_KEYS = frozenset({
    "bbox", "bboxes", "mask", "category", "defect_type",
    "confidence", "anomaly_score", "geometry_correction",
    "localization_source", "label_source",
})


def validate_vlm_output(
    raw: str | dict,
    input_box_ids: list[int] | None = None,
) -> dict:
    """Validate and normalize VLM provider output.

    Args:
        raw: JSON string or dict from provider.
        input_box_ids: Available box IDs from the defect. Used to validate
            accepted_box_ids and as default when absent.

    Returns:
        Normalized dict with observation, severity_reason, accepted_box_ids.

    Raises:
        EnrichmentValidationError on any violation.
    """
    # Parse JSON string if needed
    if isinstance(raw, str):
        stripped = raw.strip()
        # Reject markdown fences
        if stripped.startswith("```"):
            raise EnrichmentValidationError(
                "Output starts with markdown fence — reject raw JSON only."
            )
        try:
            data: dict = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise EnrichmentValidationError(f"Invalid JSON: {exc}") from exc
    elif isinstance(raw, dict):
        data = raw
    else:
        raise EnrichmentValidationError(
            f"Expected str or dict, got {type(raw).__name__}"
        )

    if not isinstance(data, dict):
        raise EnrichmentValidationError(
            f"Top-level value must be a JSON object, got {type(data).__name__}"
        )

    # Check for forbidden keys
    present_forbidden = FORBIDDEN_KEYS & data.keys()
    if present_forbidden:
        raise EnrichmentValidationError(
            f"Forbidden keys present: {sorted(present_forbidden)}"
        )

    # Check for extra keys
    extra_keys = data.keys() - ALLOWED_KEYS
    if extra_keys:
        raise EnrichmentValidationError(
            f"Extra keys not in allowed set: {sorted(extra_keys)}"
        )

    # Validate observation
    observation = data.get("observation")
    if not isinstance(observation, str) or not observation.strip():
        raise EnrichmentValidationError(
            "observation is missing, empty, or not a string."
        )
    if len(observation) > 1024:
        raise EnrichmentValidationError(
            f"observation exceeds 1024 chars ({len(observation)})."
        )

    # Validate severity_reason
    severity_reason = data.get("severity_reason")
    if not isinstance(severity_reason, str) or not severity_reason.strip():
        raise EnrichmentValidationError(
            "severity_reason is missing, empty, or not a string."
        )
    if len(severity_reason) > 512:
        raise EnrichmentValidationError(
            f"severity_reason exceeds 512 chars ({len(severity_reason)})."
        )

    # Validate accepted_box_ids
    raw_box_ids = data.get("accepted_box_ids")
    if raw_box_ids is None:
        accepted_box_ids = list(input_box_ids) if input_box_ids else []
    else:
        if not isinstance(raw_box_ids, list):
            raise EnrichmentValidationError(
                f"accepted_box_ids must be a list, got {type(raw_box_ids).__name__}."
            )
        for i, bid in enumerate(raw_box_ids):
            if not isinstance(bid, int):
                raise EnrichmentValidationError(
                    f"accepted_box_ids[{i}] is not an int: {bid!r}."
                )
        if input_box_ids is not None:
            invalid = set(raw_box_ids) - set(input_box_ids)
            if invalid:
                raise EnrichmentValidationError(
                    f"accepted_box_ids contains IDs not in input: {sorted(invalid)}."
                )
        accepted_box_ids = list(raw_box_ids)

    return {
        "observation": observation.strip(),
        "severity_reason": severity_reason.strip(),
        "accepted_box_ids": accepted_box_ids,
    }
