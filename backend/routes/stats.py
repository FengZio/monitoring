"""Statistics API for dashboard charts"""
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import func

from database import SessionLocal, Alert

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/overview")
def get_overview():
    db = SessionLocal()
    try:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        total_today = db.query(Alert).filter(Alert.timestamp >= today_start).count()
        pending = db.query(Alert).filter(
            Alert.timestamp >= today_start,
            Alert.status == "pending",
        ).count()
        resolved = db.query(Alert).filter(
            Alert.timestamp >= today_start,
            Alert.status.in_(["resolved", "dismissed"]),
        ).count()
        handle_rate = round(resolved / max(total_today, 1), 2)

        return {
            "total_today": total_today,
            "pending": pending,
            "handle_rate": handle_rate,
            "online_sources": 0,  # will be populated by frontend via /api/video/sources
        }
    finally:
        db.close()


@router.get("/daily")
def get_daily(days: int = Query(7, ge=1, le=90)):
    db = SessionLocal()
    try:
        results = []
        for i in range(days - 1, -1, -1):
            day = datetime.utcnow().date() - timedelta(days=i)
            day_start = datetime(day.year, day.month, day.day)
            day_end = day_start + timedelta(days=1)
            count = db.query(Alert).filter(
                Alert.timestamp >= day_start,
                Alert.timestamp < day_end,
            ).count()
            results.append({"date": day.isoformat(), "count": count})
        return {"daily": results}
    finally:
        db.close()


@router.get("/hourly")
def get_hourly(date: str = Query("", description="YYYY-MM-DD, defaults to today")):
    db = SessionLocal()
    try:
        if date:
            target = datetime.strptime(date, "%Y-%m-%d")
        else:
            target = datetime.utcnow()

        results = []
        for h in range(24):
            hour_start = target.replace(hour=h, minute=0, second=0, microsecond=0)
            hour_end = hour_start + timedelta(hours=1)
            count = db.query(Alert).filter(
                Alert.timestamp >= hour_start,
                Alert.timestamp < hour_end,
            ).count()
            results.append({"hour": h, "count": count})
        return {"hourly": results}
    finally:
        db.close()


@router.get("/class_distribution")
def get_class_distribution():
    db = SessionLocal()
    try:
        rows = (
            db.query(Alert.class_name, func.count(Alert.id))
            .group_by(Alert.class_name)
            .all()
        )
        total = sum(cnt for _, cnt in rows) or 1
        results = [
            {"name": name, "count": cnt, "ratio": round(cnt / total, 3)}
            for name, cnt in rows
        ]
        results.sort(key=lambda x: x["count"], reverse=True)
        return {"distribution": results}
    finally:
        db.close()


@router.get("/heatmap")
def get_heatmap(source_id: str = Query("", description="Optional source filter")):
    """Return bbox center points of all alerts for heatmap rendering."""
    db = SessionLocal()
    try:
        q = db.query(Alert.bbox).filter(Alert.bbox.isnot(None))
        if source_id:
            q = q.filter(Alert.video_source == source_id)

        points = []
        for (bbox_str,) in q.all():
            try:
                bbox = json.loads(bbox_str)
                if len(bbox) == 4:
                    cx = (bbox[0] + bbox[2]) / 2
                    cy = (bbox[1] + bbox[3]) / 2
                    points.append([round(cx, 1), round(cy, 1)])
            except (json.JSONDecodeError, TypeError):
                pass
        return {"points": points, "total": len(points)}
    finally:
        db.close()
