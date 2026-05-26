# Phase 10.1: DefectEnrichment model — async enrichment lifecycle table.
#
# Separate from defects to keep enrichment retries/status isolated.
# On success, observation/severity_reason are denormalized back to defects.

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db import Base, TZDateTime

VALID_PROVIDERS = ("edge_vlm", "template", "cloud_vlm")
VALID_STATUSES = ("pending", "running", "complete", "failed", "rejected", "skipped")


class DefectEnrichment(Base):
    __tablename__ = "defect_enrichments"
    __table_args__ = (
        UniqueConstraint(
            "defect_id", "provider", "prompt_version",
            name="uq_defect_provider_prompt",
        ),
        CheckConstraint(
            f"provider IN {VALID_PROVIDERS}",
            name="ck_enrichment_provider",
        ),
        CheckConstraint(
            f"status IN {VALID_STATUSES}",
            name="ck_enrichment_status",
        ),
        Index("ix_enrichment_status", "status"),
        Index("ix_enrichment_defect_id", "defect_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    defect_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("defects.id", ondelete="CASCADE"), nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")

    observation: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    severity_reason: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    accepted_box_ids: Mapped[list | None] = mapped_column(JSON, nullable=True, default=None)

    input_digest: Mapped[str | None] = mapped_column(String(128), nullable=True, default=None)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True, default=None)

    created_at: Mapped[datetime] = mapped_column(
        TZDateTime(), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TZDateTime(), nullable=True, default=None,
    )
