from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import get_db
from backend.app.models.defect import Defect

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
async def get_stats(
    since: datetime = Query(default=None),
    until: datetime = Query(default=None),
    bucket: Literal["hour", "day"] = Query(default="hour"),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    since_dt = since or (now - timedelta(hours=24))
    until_dt = until or now

    base = [Defect.edge_ts >= since_dt, Defect.edge_ts < until_dt]

    # total
    total = await db.scalar(
        select(func.count()).select_from(Defect).where(*base)
    ) or 0

    # by_category
    cat_rows = await db.execute(
        select(Defect.category, func.count()).where(*base).group_by(Defect.category)
    )
    by_category = {r[0]: r[1] for r in cat_rows}

    # by_severity
    sev_rows = await db.execute(
        select(Defect.severity, func.count()).where(*base).group_by(Defect.severity)
    )
    by_severity = {r[0]: r[1] for r in sev_rows}

    # timeline (SQLite strftime)
    fmt = "%Y-%m-%dT%H:00:00Z" if bucket == "hour" else "%Y-%m-%dT00:00:00Z"
    tl_rows = await db.execute(
        select(
            func.strftime(fmt, Defect.edge_ts).label("ts"),
            func.count().label("count"),
        )
        .where(*base)
        .group_by(text("ts"))
        .order_by(text("ts"))
    )
    timeline = [{"ts": r[0], "count": r[1]} for r in tl_rows]

    # ab_compare (json_extract on vlm_metrics JSON column)
    ab_rows = await db.execute(
        select(
            Defect.variant,
            func.count().label("count"),
            func.avg(
                func.json_extract(Defect.vlm_metrics, "$.json_parse_ok")
            ).label("json_ok_rate"),
            func.avg(
                func.json_extract(Defect.vlm_metrics, "$.ttft_ms")
            ).label("avg_ttft_ms"),
            func.avg(
                func.json_extract(Defect.vlm_metrics, "$.decode_tps")
            ).label("avg_decode_tps"),
            func.avg(
                func.json_extract(Defect.vlm_metrics, "$.rss_mb")
            ).label("avg_rss_mb"),
        )
        .where(*base)
        .group_by(Defect.variant)
    )
    ab_compare = {
        r.variant: {
            "count": r.count,
            "json_ok_rate": round(float(r.json_ok_rate or 0), 3),
            "avg_ttft_ms": round(float(r.avg_ttft_ms or 0), 2),
            "avg_decode_tps": round(float(r.avg_decode_tps or 0), 2),
            "avg_rss_mb": round(float(r.avg_rss_mb or 0), 1),
        }
        for r in ab_rows
    }

    return {
        "total": total,
        "by_category": by_category,
        "by_severity": by_severity,
        "timeline": timeline,
        "ab_compare": ab_compare,
    }
