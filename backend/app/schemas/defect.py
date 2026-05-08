from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

Severity = Literal["low", "medium", "high"]
Variant = Literal["A", "B"]
Stage = Literal["efficientad", "fastsam", "qwen3vl"]


class BBox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    w: float = Field(gt=0.0, le=1.0)
    h: float = Field(gt=0.0, le=1.0)


class VlmMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ttft_ms: float = Field(ge=0)
    decode_tps: float = Field(ge=0)
    prompt_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    rss_mb: float = Field(ge=0)
    json_parse_ok: bool


class DefectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: str = Field(min_length=1, max_length=32)
    category: Literal["metal_nut", "screw", "pill"]
    defect_type: str = Field(min_length=1, max_length=64)
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    anomaly_score: float = Field(ge=0)
    bboxes: list[BBox] = Field(default_factory=list, max_length=16)
    description: str = Field(default="", max_length=1024)
    variant: Variant
    edge_ts: datetime
    pipeline_ms: dict[Stage, float]
    vlm_metrics: Optional[VlmMetrics] = None
    schema_version: Literal["v1"] = "v1"

    @field_validator("edge_ts")
    @classmethod
    def must_be_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError(
                "edge_ts must be timezone-aware (ISO 8601 with offset)"
            )
        return v

    @field_validator("pipeline_ms")
    @classmethod
    def all_stages_required(cls, v: dict) -> dict:
        required = {"efficientad", "fastsam", "qwen3vl"}
        if missing := required - v.keys():
            raise ValueError(f"pipeline_ms missing stages: {missing}")
        return v


class DefectRead(DefectCreate):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    image_url: str
    server_ts: datetime


class DefectCreatedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_url: str
    server_ts: datetime
