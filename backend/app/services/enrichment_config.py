# Phase 10.1b: Enrichment configuration — immutable config from env vars.
#
# All defaults preserve current manual-only behavior (enabled=false, auto_enqueue=false).
# worker_enabled is parsed but NOT acted on in this PR.

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── Boolean parsing ───────────────────────────────────────────────────────────

_TRUTHY = {"true", "1", "yes", "on"}
_FALSY = {"false", "0", "no", "off"}


def _parse_bool(value: str, field_name: str, default: bool = False) -> bool:
    """Parse a boolean from env var string.

    Accepts: true/false, 1/0, yes/no, on/off (case-insensitive).
    Falls back to default with warning on invalid input.
    """
    normalized = value.strip().lower()
    if normalized in _TRUTHY:
        return True
    if normalized in _FALSY:
        return False
    logger.warning(
        "Invalid boolean for %s=%r, falling back to %s",
        field_name, value, default,
    )
    return default


def _parse_int(value: str, field_name: str, default: int) -> int:
    """Parse an integer from env var string. Falls back to default with warning."""
    try:
        return int(value)
    except (ValueError, TypeError):
        logger.warning(
            "Invalid integer for %s=%r, falling back to %d",
            field_name, value, default,
        )
        return default


def _parse_float(value: str, field_name: str, default: float) -> float:
    """Parse a float from env var string. Falls back to default with warning."""
    try:
        return float(value)
    except (ValueError, TypeError):
        logger.warning(
            "Invalid float for %s=%r, falling back to %s",
            field_name, value, default,
        )
        return default


# ── Config dataclass ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class EnrichmentConfig:
    """Immutable enrichment configuration. Read from environment once.

    Defaults preserve manual-only behavior:
      - enabled=false: enrichment subsystem is off
      - auto_enqueue=false: POST /api/edge/report does not create enrichment jobs
      - worker_enabled=false: no background worker loop
    """

    enabled: bool = False
    auto_enqueue: bool = False
    worker_enabled: bool = False
    provider: str = "edge_vlm"
    prompt_version: str = "phase10_1_obs_v1"
    max_per_minute: int = 10
    max_retries: int = 2
    worker_idle_sleep_s: float = 5.0
    worker_poll_interval_s: float = 2.0
    timeout_s: int = 30


def load_enrichment_config() -> EnrichmentConfig:
    """Load enrichment config from environment variables.

    Environment variables (all optional, defaults preserve current behavior):

        ENRICHMENT_ENABLED=false
        ENRICHMENT_AUTO_ENQUEUE=false
        ENRICHMENT_WORKER_ENABLED=false
        ENRICHMENT_PROVIDER=edge_vlm
        ENRICHMENT_PROMPT_VERSION=phase10_1_obs_v1
        ENRICHMENT_MAX_PER_MINUTE=10
        ENRICHMENT_MAX_RETRIES=2
        ENRICHMENT_WORKER_IDLE_SLEEP_S=5
        ENRICHMENT_WORKER_POLL_INTERVAL_S=2
        ENRICHMENT_TIMEOUT_S=30

    Does NOT read EDGE_VLM_COMMAND, EDGE_VLM_ENDPOINT, or any credentials.
    """
    return EnrichmentConfig(
        enabled=_parse_bool(
            os.environ.get("ENRICHMENT_ENABLED", "false"),
            "ENRICHMENT_ENABLED",
        ),
        auto_enqueue=_parse_bool(
            os.environ.get("ENRICHMENT_AUTO_ENQUEUE", "false"),
            "ENRICHMENT_AUTO_ENQUEUE",
        ),
        worker_enabled=_parse_bool(
            os.environ.get("ENRICHMENT_WORKER_ENABLED", "false"),
            "ENRICHMENT_WORKER_ENABLED",
        ),
        provider=os.environ.get("ENRICHMENT_PROVIDER", "edge_vlm").strip().lower(),
        prompt_version=os.environ.get(
            "ENRICHMENT_PROMPT_VERSION", "phase10_1_obs_v1",
        ).strip(),
        max_per_minute=_parse_int(
            os.environ.get("ENRICHMENT_MAX_PER_MINUTE", "10"),
            "ENRICHMENT_MAX_PER_MINUTE", 10,
        ),
        max_retries=_parse_int(
            os.environ.get("ENRICHMENT_MAX_RETRIES", "2"),
            "ENRICHMENT_MAX_RETRIES", 2,
        ),
        worker_idle_sleep_s=_parse_float(
            os.environ.get("ENRICHMENT_WORKER_IDLE_SLEEP_S", "5"),
            "ENRICHMENT_WORKER_IDLE_SLEEP_S", 5.0,
        ),
        worker_poll_interval_s=_parse_float(
            os.environ.get("ENRICHMENT_WORKER_POLL_INTERVAL_S", "2"),
            "ENRICHMENT_WORKER_POLL_INTERVAL_S", 2.0,
        ),
        timeout_s=_parse_int(
            os.environ.get("ENRICHMENT_TIMEOUT_S", "30"),
            "ENRICHMENT_TIMEOUT_S", 30,
        ),
    )
