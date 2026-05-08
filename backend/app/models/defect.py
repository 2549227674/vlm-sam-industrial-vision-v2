from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Float, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db import Base


class Defect(Base):
    __tablename__ = "defects"
    __table_args__ = (
        UniqueConstraint("line_id", "edge_ts", name="uq_line_edge_ts"),
        CheckConstraint("variant IN ('A', 'B')", name="ck_variant"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    image_url: Mapped[str] = mapped_column(String(255))
    server_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    line_id: Mapped[str] = mapped_column(String(32), index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    defect_type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    anomaly_score: Mapped[float] = mapped_column(Float)

    bboxes: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(String(1024), default="")

    variant: Mapped[str] = mapped_column(String(2), index=True)
    edge_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    pipeline_ms: Mapped[dict] = mapped_column(JSON)
    vlm_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    schema_version: Mapped[str] = mapped_column(String(8), default="v1")
