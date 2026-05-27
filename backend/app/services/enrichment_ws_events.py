# Phase 10.1b-4: Enrichment WebSocket event builder and error sanitizer.
#
# Small helper for constructing enrichment lifecycle events and
# sanitizing error messages before broadcast.

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Literal

EnrichmentWsStatus = Literal[
    "pending", "running", "complete", "rejected", "failed",
]

# Patterns to strip from error messages before sending to frontend.
_SANITIZE_PATTERNS: list[re.Pattern[str]] = [
    # Filesystem paths
    re.compile(r"/[\w./\-]+"),
    # IP addresses (v4)
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    # Tokens / keys / secrets
    re.compile(r"(?:token|key|secret|password|api_key)[=:]\s*\S+", re.IGNORECASE),
    # sshpass patterns (redact everything after sshpass on same line)
    re.compile(r"sshpass\s+.*", re.IGNORECASE),
    # Environment variable values that look like commands
    re.compile(r"EDGE_VLM_COMMAND[=:]\s*\S+", re.IGNORECASE),
    # Stack trace file:line patterns
    re.compile(r'File ".*?", line \d+', re.IGNORECASE),
]

_MAX_ERROR_LEN = 200


def sanitize_error_message(raw: str | None) -> str | None:
    """Sanitize an error string for safe frontend display.

    Removes:
      - Filesystem paths
      - IP addresses
      - Tokens/keys/secrets/passwords
      - sshpass patterns
      - EDGE_VLM_COMMAND values
      - Stack trace file:line patterns

    Returns None if input is None or becomes empty after sanitization.
    Truncated to _MAX_ERROR_LEN characters.
    """
    if raw is None:
        return None

    text = raw.strip()
    if not text:
        return None

    for pattern in _SANITIZE_PATTERNS:
        text = pattern.sub("[redacted]", text)

    # Collapse multiple redactions
    text = re.sub(r"(?:\[redacted\]\s*){2,}", "[redacted] ", text)
    text = text.strip()

    if not text:
        return None

    if len(text) > _MAX_ERROR_LEN:
        text = text[:_MAX_ERROR_LEN] + "..."

    return text


# Fields that the event payload may contain (informational, not mutated).
_UPDATED_FIELDS_BY_STATUS: dict[str, list[str]] = {
    "pending": [],
    "running": [],
    "complete": ["observation", "severity_reason", "observation_source"],
    "rejected": [],
    "failed": [],
}


def build_enrichment_event(
    *,
    defect_id: int,
    enrichment_id: int,
    status: EnrichmentWsStatus,
    provider: str,
    observation_source: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    """Build a defect_enrichment_updated WebSocket event payload.

    Args:
        defect_id: The defect this enrichment belongs to.
        enrichment_id: The enrichment job ID.
        status: Current enrichment lifecycle status.
        provider: Provider name (template, edge_vlm, cloud_vlm).
        observation_source: Source of observation (same as provider on success).
        error_message: Raw error message (will be sanitized).

    Returns:
        JSON-serializable dict for WebSocket broadcast.
    """
    return {
        "type": "defect_enrichment_updated",
        "defect_id": defect_id,
        "enrichment_id": enrichment_id,
        "status": status,
        "provider": provider,
        "observation_source": observation_source,
        "updated_fields": _UPDATED_FIELDS_BY_STATUS.get(status, []),
        "error_message": sanitize_error_message(error_message),
        "ts": datetime.now(timezone.utc).isoformat(),
    }
