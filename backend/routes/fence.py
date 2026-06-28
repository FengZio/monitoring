"""Fence CRUD routes -- multi-source support"""
import json

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database import SessionLocal, Fence
from stream_bridge import stream_manager

router = APIRouter(prefix="/api/fence", tags=["fence"])


class FencePayload(BaseModel):
    points: list[list[float]]
    mode: str = 'restricted'


# ==================== Fence ====================

@router.get("")
def get_fence(source_id: str = Query("default")):
    db = SessionLocal()
    try:
        fence = db.query(Fence).filter(Fence.source_id == source_id).first()

        result = {
            "source_id": source_id,
            "points": [],
            "enabled": False,
            "mode": "restricted",
        }
        if fence:
            result["points"] = json.loads(fence.points or "[]")
            result["enabled"] = fence.enabled
            result["mode"] = fence.mode or "restricted"
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