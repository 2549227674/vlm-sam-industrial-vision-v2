import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.db import Base, engine
import backend.app.models  # noqa: F401 — ensure Defect is registered with Base.metadata
from backend.app.ws.manager import ConnectionManager

logger = logging.getLogger(__name__)

_DEFECT_STORAGE_DIR = os.environ.get("DEFECT_STORAGE_DIR")
if _DEFECT_STORAGE_DIR:
    _STATIC_DIR = Path(_DEFECT_STORAGE_DIR).parent
    _DEFECT_DIR = Path(_DEFECT_STORAGE_DIR)
else:
    _STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
    _DEFECT_DIR = _STATIC_DIR / "defects"

_EDGE_UPLOAD_TOKEN = os.environ.get("EDGE_UPLOAD_TOKEN", "")


async def _auth_middleware(request: Request, call_next):
    if (
        _EDGE_UPLOAD_TOKEN
        and request.method == "POST"
        and request.url.path == "/api/edge/report"
    ):
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer ") or auth.removeprefix("Bearer ").strip() != _EDGE_UPLOAD_TOKEN:
            return JSONResponse(
                status_code=401,
                content={"error": {"code": "UNAUTHORIZED", "message": "Missing or invalid upload token"}},
            )
    return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    os.makedirs(_DEFECT_DIR, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.state.ws_manager = ConnectionManager()
    await app.state.ws_manager.start_heartbeat()

    # Optional enrichment worker loop (Phase 10.1b-2)
    # Starts only when both flags are true. Defaults off.
    app.state.enrichment_worker_task = None
    from backend.app.services.enrichment_config import load_enrichment_config
    enrichment_cfg = load_enrichment_config()
    if enrichment_cfg.enabled and enrichment_cfg.worker_enabled:
        from backend.app.db import async_session
        from backend.app.services.enrichment_worker_loop import enrichment_worker_loop
        app.state.enrichment_worker_task = asyncio.create_task(
            enrichment_worker_loop(
                enrichment_cfg,
                create_session_factory=async_session,
            ),
        )
        logger.info(
            "Enrichment worker loop task started "
            "(provider=%s, max_per_minute=%d)",
            enrichment_cfg.provider, enrichment_cfg.max_per_minute,
        )

    yield

    # shutdown
    if app.state.enrichment_worker_task is not None:
        app.state.enrichment_worker_task.cancel()
        try:
            await app.state.enrichment_worker_task
        except asyncio.CancelledError:
            pass
        logger.info("Enrichment worker loop task stopped")

    await app.state.ws_manager.stop_heartbeat()
    await engine.dispose()


app = FastAPI(
    title="Industrial Vision API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "SCHEMA_MISMATCH", "message": str(exc.errors())}},
    )

# CORS — configurable via CORS_ORIGINS env var (comma-separated)
_cors_env = os.environ.get("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()] if _cors_env else []

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://localhost(:\d+)?",
    allow_origins=_cors_origins if _cors_origins else ["https://vision.example.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
    max_age=3600,
)

# Auth middleware for upload token (runs before FastAPI form validation)
app.add_middleware(BaseHTTPMiddleware, dispatch=_auth_middleware)

# Static files
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# Routers
from backend.app.routers import defects, edge, enrichment, health, stats, ws  # noqa: E402

app.include_router(edge.router)
app.include_router(defects.router)
app.include_router(enrichment.router)
app.include_router(stats.router)
app.include_router(health.router)
app.include_router(ws.router)
