# Phase 10.1b-2: Enrichment worker loop — polls and processes pending jobs.
#
# Starts only when ENRICHMENT_ENABLED=true AND ENRICHMENT_WORKER_ENABLED=true.
# Reuses process_next_pending_enrichment() from enrichment_worker.py.
# Single-process only: production multi-worker must keep this disabled
# until DB-level locking (e.g. SKIP LOCKED) is introduced.
#
# Does NOT call provider during /api/edge/report.
# Does NOT implement HTTP mode, cloud_vlm, retry schema, or WebSocket events.

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque

from backend.app.services.enrichment_config import EnrichmentConfig
from backend.app.services.enrichment_worker import process_next_pending_enrichment
from backend.app.services.provider_factory import get_provider
from backend.app.services.vlm_provider import (
    ProviderConfigError,
    ProviderUnavailableError,
    VlmProvider,
    VlmProviderError,
)

logger = logging.getLogger(__name__)


class _RateLimiter:
    """Simple sliding-window rate limiter (in-memory, single-process)."""

    def __init__(self, max_per_minute: int) -> None:
        self._max = max(1, max_per_minute)
        self._timestamps: deque[float] = deque()

    def allow(self) -> bool:
        now = time.monotonic()
        cutoff = now - 60.0
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
        return len(self._timestamps) < self._max

    def record(self) -> None:
        self._timestamps.append(time.monotonic())

    @property
    def wait_seconds(self) -> float:
        """Seconds until the oldest entry expires from the window."""
        if not self._timestamps or len(self._timestamps) < self._max:
            return 0.0
        return max(0.0, self._timestamps[0] + 60.0 - time.monotonic())


def _build_provider(config: EnrichmentConfig) -> VlmProvider:
    """Build provider from config. Does not read EDGE_VLM_COMMAND from config."""
    import os

    return get_provider(
        config.provider,
        edge_vlm_mode=os.environ.get("EDGE_VLM_MODE", "disabled"),
        edge_vlm_command=os.environ.get("EDGE_VLM_COMMAND") or None,
        edge_vlm_endpoint=os.environ.get("EDGE_VLM_ENDPOINT") or None,
        edge_vlm_model_name=os.environ.get("EDGE_VLM_MODEL_NAME", "qwen3-vl-2b-base"),
        timeout_s=config.timeout_s,
    )


async def enrichment_worker_loop(
    config: EnrichmentConfig,
    *,
    create_session_factory,
    provider: VlmProvider | None = None,
    ws_manager: object | None = None,
) -> None:
    """Main worker loop. Runs until cancelled.

    Args:
        config: EnrichmentConfig (immutable).
        create_session_factory: Callable returning an async context manager
            that yields an AsyncSession. Typically the async_sessionmaker itself.
        provider: VlmProvider instance. If None, built from config + env.

    This coroutine is designed to be wrapped in an asyncio.Task and cancelled
    during FastAPI lifespan shutdown.
    """
    if provider is None:
        try:
            provider = _build_provider(config)
        except (
            ProviderConfigError, ProviderUnavailableError, VlmProviderError, ValueError,
        ) as exc:
            logger.error(
                "Enrichment worker loop aborting: provider construction failed: %s", exc,
            )
            return

    limiter = _RateLimiter(config.max_per_minute)

    logger.info(
        "Enrichment worker loop started (provider=%s, max_per_minute=%d, "
        "poll_interval=%.1fs, idle_sleep=%.1fs)",
        provider.provider_name,
        config.max_per_minute,
        config.worker_poll_interval_s,
        config.worker_idle_sleep_s,
    )

    try:
        while True:
            # Rate limit gate
            if not limiter.allow():
                wait = limiter.wait_seconds
                if wait > 0:
                    logger.debug("Rate limited, sleeping %.2fs", wait)
                    await asyncio.sleep(wait)
                    continue

            # Poll for oldest pending job
            processed = await _poll_once(config, create_session_factory, provider, ws_manager)

            if processed:
                limiter.record()
                logger.info(
                    "Worker processed enrichment %d (status=%s)",
                    processed.id, processed.status,
                )
                # Respect poll interval between jobs
                await asyncio.sleep(config.worker_poll_interval_s)
            else:
                # No pending jobs — idle sleep
                await asyncio.sleep(config.worker_idle_sleep_s)

    except asyncio.CancelledError:
        logger.info("Enrichment worker loop shutting down (cancelled)")
        raise


async def _poll_once(
    config: EnrichmentConfig,
    create_session_factory,
    provider: VlmProvider,
    ws_manager: object | None = None,
):
    """Process one pending job (if any). Returns the enrichment or None."""
    async with create_session_factory() as db:
        try:
            result = await process_next_pending_enrichment(db, provider=provider, ws_manager=ws_manager)
            await db.commit()
            return result
        except Exception:
            await db.rollback()
            logger.exception("Worker poll cycle error")
            return None
