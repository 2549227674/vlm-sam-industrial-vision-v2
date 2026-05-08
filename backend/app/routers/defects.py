from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import get_db
from backend.app.models.defect import Defect
from backend.app.schemas.defect import DefectRead, PaginatedDefectsResponse

router = APIRouter(prefix="/api/defects", tags=["defects"])

SORTABLE_FIELDS = {
    "id", "edge_ts", "server_ts", "severity",
    "confidence", "anomaly_score", "category", "variant",
}


@router.get("", response_model=PaginatedDefectsResponse)
async def list_defects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    severity: Optional[str] = None,
    variant: Optional[str] = None,
    line_id: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    sort: str = Query("-edge_ts"),
    db: AsyncSession = Depends(get_db),
):
    query = select(Defect)

    if category:
        query = query.where(Defect.category == category)
    if severity:
        query = query.where(Defect.severity == severity)
    if variant:
        query = query.where(Defect.variant == variant)
    if line_id:
        query = query.where(Defect.line_id == line_id)
    if since:
        query = query.where(Defect.edge_ts >= since)
    if until:
        query = query.where(Defect.edge_ts < until)

    count_q = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_q) or 0

    # sort whitelist
    sort_field = sort.lstrip("-")
    if sort_field not in SORTABLE_FIELDS:
        sort_field = "edge_ts"
        descending = True
    else:
        descending = sort.startswith("-")
    col = getattr(Defect, sort_field)
    query = query.order_by(desc(col) if descending else asc(col))

    query = query.offset((page - 1) * page_size).limit(page_size)
    rows = await db.execute(query)
    items = rows.scalars().all()

    return PaginatedDefectsResponse(
        items=[DefectRead.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{defect_id}")
async def get_defect(defect_id: int, db: AsyncSession = Depends(get_db)):
    defect = await db.get(Defect, defect_id)
    if not defect:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "NOT_FOUND", "message": f"Defect {defect_id} not found"}},
        )
    return DefectRead.model_validate(defect)
