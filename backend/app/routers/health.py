import time

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import get_db

router = APIRouter(prefix="/api", tags=["health"])

_START = time.time()


@router.get("/health")
async def health_check(request: Request, db: AsyncSession = Depends(get_db)):
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    ws_manager = getattr(request.app.state, "ws_manager", None)
    ws_clients = (
        sum(len(c) for c in ws_manager._rooms.values()) if ws_manager else 0
    )

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "version": "v1",
        "uptime_s": int(time.time() - _START),
        "db": db_status,
        "ws_clients": ws_clients,
    }
