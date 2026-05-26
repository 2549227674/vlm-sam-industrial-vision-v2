# Phase 10.1: Pydantic schemas for defect enrichment API.

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

EnrichmentStatus = Literal[
    "pending", "running", "complete", "failed", "rejected", "skipped",
]
EnrichmentProvider = Literal["edge_vlm", "template", "cloud_vlm"]


class EnrichmentCreatedResponse(BaseModel):
    """Returned by POST /api/defects/{id}/enrich on 202 Accepted."""
    model_config = ConfigDict(from_attributes=True)

    enrichment_id: int
    defect_id: int
    status: EnrichmentStatus


class DefectEnrichmentRead(BaseModel):
    """Returned by GET /api/defects/{id}/enrichment."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    defect_id: int
    provider: EnrichmentProvider
    provider_model: str
    prompt_version: str
    status: EnrichmentStatus
    observation: Optional[str] = None
    severity_reason: Optional[str] = None
    accepted_box_ids: Optional[list[int]] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
