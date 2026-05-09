import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.db import Base, engine
import backend.app.models  # noqa: F401 — ensure Defect is registered with Base.metadata
from backend.app.ws.manager import ConnectionManager

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    os.makedirs(_STATIC_DIR / "defects", exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.state.ws_manager = ConnectionManager()
    await app.state.ws_manager.start_heartbeat()
    yield
    # shutdown
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

# CORS — registered first to handle OPTIONS preflight
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://vision.example.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
    max_age=3600,
)

# Static files
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# Routers
from backend.app.routers import defects, edge, health, stats, ws  # noqa: E402

app.include_router(edge.router)
app.include_router(defects.router)
app.include_router(stats.router)
app.include_router(health.router)
app.include_router(ws.router)
