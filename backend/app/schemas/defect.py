from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

Severity = Literal["low", "medium", "high"]
# v1.1: 新增 4 变体，保留 A/B 向下兼容
VALID_VARIANTS = {"2B_base", "2B_lora", "4B_base", "4B_lora", "A", "B"}

# v1.3: accept both old stage keys (fastsam/qwen3vl) and new ones (localizer/enrichment)
Stage = Literal["efficientad", "fastsam", "qwen3vl", "localizer", "upload", "enrichment"]


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


class TraceEvent(BaseModel):
    """Chrome Trace format single complete event.

    ts/dur unit: microseconds, origin=0 corresponds to frame start.
    extra="ignore" to accept future C++ / Perfetto extension fields (args/pid).
    """

    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1, max_length=128)
    ts: float = Field(ge=0)
    dur: float = Field(ge=0)
    tid: str = Field(min_length=1, max_length=64)
    ph: Literal["X"]
    cat: str = Field(default="", max_length=64)


class DefectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: str = Field(min_length=1, max_length=32)
    category: Literal[
        "bottle", "cable", "capsule", "carpet", "grid", "hazelnut",
        "leather", "metal_nut", "pill", "screw", "tile", "toothbrush",
        "transistor", "wood", "zipper",
    ]
    defect_type: str = Field(min_length=1, max_length=64)
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    anomaly_score: float = Field(ge=0)
    bboxes: list[BBox] = Field(default_factory=list, max_length=16)
    description: str = Field(default="", max_length=1024)
    variant: str
    edge_ts: datetime
    pipeline_ms: dict[Stage, float]
    vlm_metrics: Optional[VlmMetrics] = None
    trace_events: Optional[list[TraceEvent]] = Field(default=None, max_length=64)
    schema_version: Literal["v1"] = "v1"

    # v1.3: source fields (all optional for backward compat)
    localization_source: Optional[str] = Field(default=None, max_length=64)
    label_source: Optional[str] = Field(default=None, max_length=64)
    observation_source: Optional[str] = Field(default=None, max_length=64)
    defect_family: Optional[str] = Field(default=None, max_length=64)
    observation: Optional[str] = Field(default=None, max_length=1024)
    severity_reason: Optional[str] = Field(default=None, max_length=512)

    @field_validator("edge_ts")
    @classmethod
    def must_be_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError(
                "edge_ts must be timezone-aware (ISO 8601 with offset)"
            )
        return v

    @field_validator("variant")
    @classmethod
    def validate_variant(cls, v: str) -> str:
        if v not in VALID_VARIANTS:
            raise ValueError(f"variant must be one of {VALID_VARIANTS}, got '{v}'")
        return v

    @field_validator("pipeline_ms")
    @classmethod
    def all_stages_required(cls, v: dict) -> dict:
        # v1.3: accept either old (fastsam/qwen3vl) or new (localizer) stage keys
        old_required = {"efficientad", "fastsam", "qwen3vl"}
        new_required = {"efficientad", "localizer", "upload"}
        if old_required <= v.keys():
            return v
        if new_required <= v.keys():
            return v
        # Backward compat: if fastsam present but localizer not, accept (deprecated)
        if "efficientad" in v and "fastsam" in v:
            return v
        # Fall through: report what's missing from the new scheme
        missing = new_required - v.keys()
        raise ValueError(f"pipeline_ms missing stages: {missing}")


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


class PaginatedDefectsResponse(BaseModel):
    items: list[DefectRead]
    total: int
    page: int
    page_size: int
