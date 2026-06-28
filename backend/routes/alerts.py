"""告警历史查询 + 处理工作流路由"""
import datetime
import os

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from database import SessionLocal, Alert

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertStatusUpdate(BaseModel):
    status: str          # pending / processing / dismissed / resolved
    handler: str = ""
    opinion: str = ""


VALID_STATUSES = {"pending", "processing", "dismissed", "resolved"}


def _alert_to_dict(r: Alert) -> dict:
    return {
        "id": r.id,
        "class_name": r.class_name,
        "confidence": r.confidence,
        "bbox": r.bbox,
        "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        "video_source": r.video_source,
        "snapshot_path": r.snapshot_path,
        "clip_path": r.clip_path,
        "handled": r.handled,
        "status": r.status or "pending",
        "handler": r.handler,
        "opinion": r.opinion,
        "handled_at": r.handled_at.isoformat() if r.handled_at else None,
    }


@router.get("")
def list_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query("", description="Filter by status: pending/processing/dismissed/resolved"),
    source_id: str = Query("", description="Filter by video source id"),
):
    db = SessionLocal()
    try:
        q = db.query(Alert)
        if status and status in VALID_STATUSES:
            q = q.filter(Alert.status == status)
        if source_id:
            q = q.filter(Alert.video_source == source_id)
        total = q.count()
        rows = (
            q.order_by(Alert.timestamp.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        items = [_alert_to_dict(r) for r in rows]
        return {"total": total, "page": page, "page_size": page_size, "items": items}
    finally:
        db.close()


@router.patch("/{alert_id}/status")
def update_alert_status(alert_id: int, payload: AlertStatusUpdate):
    if payload.status not in VALID_STATUSES:
        raise HTTPException(400, f"Invalid status: {payload.status}")

    db = SessionLocal()
    try:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            raise HTTPException(404, "Alert not found")

        alert.status = payload.status
        alert.handler = payload.handler or alert.handler
        alert.opinion = payload.opinion or alert.opinion
        alert.handled_at = datetime.datetime.utcnow()
        if payload.status in ("dismissed", "resolved"):
            alert.handled = True
        db.commit()
        return {"status": "updated", "alert": _alert_to_dict(alert)}
    finally:
        db.close()


@router.get("/{alert_id}/clip")
def get_alert_clip(alert_id: int):
    db = SessionLocal()
    try:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert or not alert.clip_path:
            raise HTTPException(404, "Clip not found")
        clip_path = alert.clip_path
        if not os.path.isfile(clip_path):
            raise HTTPException(404, "Clip file does not exist on disk")
        return FileResponse(clip_path, media_type="video/mp4", filename=os.path.basename(clip_path))
    finally:
        db.close()
