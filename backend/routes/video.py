"""视频源管理路由 — multi-source support"""
import os
import uuid
import base64

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

import cv2
from config import UPLOADS_DIR
from stream_bridge import stream_manager

router = APIRouter(prefix="/api/video", tags=["video"])


class WebcamStart(BaseModel):
    camera_id: int = 0


# ---- Upload ----

@router.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "No file provided")

    ext = os.path.splitext(file.filename)[1] or ".mp4"
    unique_name = f"{uuid.uuid4().hex[:8]}{ext}"
    dest = UPLOADS_DIR / unique_name
    with open(dest, "wb") as f:
        f.write(await file.read())
    return {"filename": unique_name, "path": str(dest)}


# ---- Source management ----

@router.post("/sources/webcam")
async def add_webcam_source(body: WebcamStart):
    try:
        source_id = stream_manager.add_source("webcam", str(body.camera_id))
        return {"status": "ok", "source_id": source_id, "source": f"webcam:{body.camera_id}"}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/sources/file/{filename}")
async def add_file_source(filename: str):
    path = UPLOADS_DIR / filename
    if not path.exists():
        raise HTTPException(404, "video file not found")
    try:
        source_id = stream_manager.add_source("file", str(path))
        return {"status": "ok", "source_id": source_id, "source": filename}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/sources/{source_id}")
async def remove_source(source_id: str):
    ok = stream_manager.remove_source(source_id)
    if not ok:
        raise HTTPException(404, "source not found")
    return {"status": "removed", "source_id": source_id}


@router.get("/sources")
async def list_sources():
    return {"sources": stream_manager.get_sources()}


# ---- Preview ----

@router.post("/preview/webcam")
async def preview_webcam(camera_id: int = 0):
    cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise HTTPException(500, f"Cannot open webcam {camera_id}")
    try:
        ret, frame = cap.read()
        if not ret:
            raise HTTPException(500, "Cannot read frame from webcam")
        h, w = frame.shape[:2]
        _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return {"frame": base64.b64encode(jpeg).decode(), "width": w, "height": h}
    finally:
        cap.release()


@router.post("/preview/file/{filename}")
async def preview_file(filename: str):
    video_path = UPLOADS_DIR / filename
    if not video_path.exists():
        raise HTTPException(404, "Video file not found")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise HTTPException(500, f"Cannot open video: {filename}")
    try:
        ret, frame = cap.read()
        if not ret:
            raise HTTPException(500, "Cannot read frame from video")
        h, w = frame.shape[:2]
        _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return {"frame": base64.b64encode(jpeg).decode(), "width": w, "height": h}
    finally:
        cap.release()


@router.get("/list")
async def list_videos():
    files = []
    for f in UPLOADS_DIR.iterdir():
        if f.is_file() and f.suffix.lower() in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
            files.append({"filename": f.name, "size": f.stat().st_size})
    return {"videos": files}
