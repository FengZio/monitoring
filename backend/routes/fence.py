"""Fence CRUD + spatial calibration routes -- multi-source support"""
import json

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database import SessionLocal, Fence, Calibration
from stream_bridge import stream_manager

router = APIRouter(prefix="/api/fence", tags=["fence"])


class FencePayload(BaseModel):
    points: list[list[float]]
    mode: str = 'restricted'


class CalibrationPayload(BaseModel):
    pixel_points: list[list[float]]
    world_points: list[list[float]]


# ==================== Fence ====================

@router.get("")
def get_fence(source_id: str = Query("default")):
    db = SessionLocal()
    try:
        fence = db.query(Fence).filter(Fence.source_id == source_id).first()
        cal = db.query(Calibration).filter(Calibration.source_id == source_id).first()

        result = {
            "source_id": source_id,
            "points": [],
            "enabled": False,
            "mode": "restricted",
            "has_calibration": False,
            "pixel_points": [],
            "world_points": [],
        }
        if fence:
            result["points"] = json.loads(fence.points or "[]")
            result["enabled"] = fence.enabled
            result["mode"] = fence.mode or "restricted"
        if cal and cal.pixel_points and cal.world_points:
            result["has_calibration"] = True
            result["pixel_points"] = json.loads(cal.pixel_points)
            result["world_points"] = json.loads(cal.world_points)
        return result
    finally:
        db.close()


@router.post("")
def save_fence(payload: FencePayload, source_id: str = Query("default")):
    if len(payload.points) < 3:
        raise HTTPException(400, "Need at least 3 points")

    db = SessionLocal()
    try:
        fence = db.query(Fence).filter(Fence.source_id == source_id).first()
        if not fence:
            fence = Fence(source_id=source_id, points=json.dumps([]))
            db.add(fence)
        fence.points = json.dumps(payload.points)
        fence.mode = payload.mode
        db.commit()

        # Update in-memory fence checker if source is active
        fc = stream_manager.get_fence_checker(source_id)
        if fc:
            fc.set_fence(payload.points, mode=payload.mode)

        return {"status": "saved", "source_id": source_id}
    finally:
        db.close()


@router.delete("")
def clear_fence(source_id: str = Query("default")):
    db = SessionLocal()
    try:
        fence = db.query(Fence).filter(Fence.source_id == source_id).first()
        if fence:
            fence.points = json.dumps([])
            fence.enabled = False
            db.commit()

        fc = stream_manager.get_fence_checker(source_id)
        if fc:
            fc.set_fence([])

        return {"status": "cleared", "source_id": source_id}
    finally:
        db.close()


# ==================== Calibration ====================

@router.post("/calibrate")
def save_calibration(payload: CalibrationPayload, source_id: str = Query("default")):
    if len(payload.pixel_points) != 4 or len(payload.world_points) != 4:
        raise HTTPException(400, "Need exactly 4 pixel and 4 world points")

    db = SessionLocal()
    try:
        cal = db.query(Calibration).filter(Calibration.source_id == source_id).first()
        if not cal:
            cal = Calibration(source_id=source_id, pixel_points="[]", world_points="[]")
            db.add(cal)
        cal.pixel_points = json.dumps(payload.pixel_points)
        cal.world_points = json.dumps(payload.world_points)
        db.commit()

        fc = stream_manager.get_fence_checker(source_id)
        reprojected = False
        fence_px = []
        if fc:
            try:
                fc.set_calibration(payload.pixel_points, payload.world_points)
                if fc.has_calibration and fc.has_fence:
                    fence_px = fc.get_fence_pixels()
                    reprojected = True
            except Exception:
                pass

        return {
            "status": "saved",
            "source_id": source_id,
            "fence_pixels": fence_px,
            "reprojected": reprojected,
        }
    finally:
        db.close()


@router.delete("/calibrate")
def clear_calibration(source_id: str = Query("default")):
    db = SessionLocal()
    try:
        cal = db.query(Calibration).filter(Calibration.source_id == source_id).first()
        if cal:
            cal.pixel_points = json.dumps([])
            cal.world_points = json.dumps([])
            db.commit()
        return {"status": "cleared", "source_id": source_id}
    finally:
        db.close()


# ==================== Fence mode ====================

@router.post("/mode")
def set_fence_mode(mode: str, source_id: str = Query("default")):
    if mode not in ("restricted", "enclosure"):
        raise HTTPException(400, "Mode must be restricted or enclosure")
    db = SessionLocal()
    try:
        fence = db.query(Fence).filter(Fence.source_id == source_id).first()
        if fence:
            fence.mode = mode
            db.commit()
        return {"status": "updated", "mode": mode, "source_id": source_id}
    finally:
        db.close()
