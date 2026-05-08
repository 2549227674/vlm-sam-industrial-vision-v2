import json
import os
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import get_db
from backend.app.models.defect import Defect
from backend.app.schemas.defect import DefectCreatedResponse, DefectCreate

router = APIRouter(prefix="/api/edge", tags=["edge"])

_STATIC_DEFECTS = Path(__file__).resolve().parent.parent.parent / "static" / "defects"
MAX_IMAGE_SIZE = 2 * 1024 * 1024  # 2 MB


def _error(status_code: int, code: str, message: str, details=None):
    content: dict = {"error": {"code": code, "message": message}}
    if details is not None:
        content["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=content)


@router.post("/report", response_model=DefectCreatedResponse)
async def report_defect(
    request: Request,
    image: UploadFile = File(...),
    meta: str = Form(...),
    crop: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
):
    # --- 415: Content-Type guard ---
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        return _error(415, "UNSUPPORTED_MEDIA_TYPE", "Must be multipart/form-data")

    # --- 400: JSON parse + 422: schema_version check (before Pydantic) ---
    try:
        raw = json.loads(meta)
    except (json.JSONDecodeError, TypeError):
        return _error(400, "VALIDATION_ERROR", "meta must be valid JSON")

    if raw.get("schema_version") != "v1":
        return _error(
            422, "SCHEMA_MISMATCH",
            f"Unsupported schema_version: {raw.get('schema_version')!r}",
        )

    # --- 400: Pydantic full validation ---
    try:
        meta_data = DefectCreate.model_validate(raw)
    except ValidationError as e:
        return _error(400, "VALIDATION_ERROR", "meta field validation failed", e.errors())

    # --- 400: BBox secondary validation (x+w≤1, y+h≤1) ---
    for bbox in meta_data.bboxes:
        if bbox.x + bbox.w > 1.0 or bbox.y + bbox.h > 1.0:
            return _error(
                400, "VALIDATION_ERROR",
                f"BBox (x={bbox.x}, w={bbox.w}, y={bbox.y}, h={bbox.h}) "
                "exceeds normalized bounds (x+w≤1, y+h≤1)",
            )

    # --- 400: image type ---
    if image.content_type not in ("image/jpeg", "image/jpg"):
        return _error(400, "INVALID_IMAGE", "Only JPEG images are allowed")

    # --- stream image to disk (async, 1 MB chunks) ---
    date_str = meta_data.edge_ts.strftime("%Y%m%d")
    save_dir = _STATIC_DEFECTS / date_str
    os.makedirs(save_dir, exist_ok=True)

    file_id = uuid.uuid4().hex
    filepath = save_dir / f"{file_id}.jpg"
    image_size = 0

    try:
        async with aiofiles.open(filepath, "wb") as buf:
            while chunk := await image.read(1024 * 1024):
                image_size += len(chunk)
                if image_size > MAX_IMAGE_SIZE:
                    await buf.close()
                    os.remove(filepath)
                    return _error(413, "PAYLOAD_TOO_LARGE", "Image exceeds 2 MB limit")
                await buf.write(chunk)
    except Exception:
        if filepath.exists():
            filepath.unlink()
        return _error(500, "INTERNAL_ERROR", "Failed to save image")

    image_url = f"/static/defects/{date_str}/{file_id}.jpg"

    # --- write to DB ---
    db_defect = Defect(
        image_url=image_url,
        line_id=meta_data.line_id,
        category=meta_data.category,
        defect_type=meta_data.defect_type,
        severity=meta_data.severity,
        confidence=meta_data.confidence,
        anomaly_score=meta_data.anomaly_score,
        bboxes=[b.model_dump() for b in meta_data.bboxes],
        description=meta_data.description,
        variant=meta_data.variant,
        edge_ts=meta_data.edge_ts,
        pipeline_ms=meta_data.pipeline_ms,
        vlm_metrics=meta_data.vlm_metrics.model_dump() if meta_data.vlm_metrics else None,
        schema_version=meta_data.schema_version,
    )
    db.add(db_defect)

    try:
        await db.flush()
        await db.refresh(db_defect)
    except IntegrityError:
        await db.rollback()
        if filepath.exists():
            filepath.unlink()
        return _error(409, "DUPLICATE_REPORT", "Same line_id + edge_ts already exists")

    # --- build 3-field response (avoid ORM→Pydantic round-trip; SQLite loses tzinfo) ---
    resp = DefectCreatedResponse(
        id=db_defect.id,
        image_url=db_defect.image_url,
        server_ts=db_defect.server_ts,
    )

    # --- WebSocket broadcast ---
    ws_manager = getattr(request.app.state, "ws_manager", None)
    if ws_manager:
        await ws_manager.broadcast(
            "dashboard",
            {
                "type": "defect_created",
                "data": {
                    "id": db_defect.id,
                    "image_url": db_defect.image_url,
                    "server_ts": db_defect.server_ts.isoformat(),
                    "line_id": meta_data.line_id,
                    "category": meta_data.category,
                    "severity": meta_data.severity,
                    "variant": meta_data.variant,
                },
            },
        )

    return resp
