"""Multi-source video processing with threading (shared model, fast startup)"""
import asyncio
import json
import logging
import os
import time
import traceback
from collections import deque
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty
from threading import Thread, Event, Lock
from typing import Optional, Set
from uuid import uuid4

import cv2
import numpy as np

from config import SNAPSHOTS_DIR
from database import SessionLocal, Alert, Fence, Config
from notifier import send_alert_notification
from sse_manager import sse_broadcaster
from routes.ws_stream import ws_broadcaster, encode_frame
from detector import Detector
from identity_resolver import IdentityResolver
from pose_detector import PoseDetector
from source_tracker import SourceTracker
from fence_checker import FenceChecker
from vllm_client import annotate_panorama_frames, analyze_frames, compose_context_frames, crop_alert_frames, select_adaptive_frames

logger = logging.getLogger(__name__)

CLIPS_DIR = Path(__file__).resolve().parent / "uploads" / "clips"
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Thread worker (model shared via Detector singleton)
# ---------------------------------------------------------------------------

def _source_worker(
    source_id: str,
    source_type: str,
    source_arg: str,
    result_queue: Queue,
    stop_event: Event,
    detector: Detector,
    pose_detector: PoseDetector,
    source_tracker: SourceTracker,
    fence_checker: FenceChecker,
    ring_buffer: deque,
    ring_buffer_lock: Lock,
) -> None:
    """Runs in a thread: open source -> detect -> check fence -> encode -> send."""
    try:
        identity_resolver = IdentityResolver()
        if source_type == "webcam":
            cam_id = int(source_arg)
            cap = cv2.VideoCapture(cam_id, cv2.CAP_DSHOW)
            fps = 25.0
            is_live = True
        else:
            cap = cv2.VideoCapture(source_arg)
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            is_live = False

        if not cap.isOpened():
            result_queue.put({"source_id": source_id, "type": "error", "error": "Cannot open source"})
            return

        frame_idx = 0

        # Alert clip writer state
        clip_writer: Optional[cv2.VideoWriter] = None
        clip_frames_remaining = 0

        result_queue.put({
            "source_id": source_id,
            "type": "ready",
            "fps": fps,
        })

        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                if not is_live:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                time.sleep(0.5)
                continue

            frame_idx += 1
            h, w = frame.shape[:2]

            # Use native resolution (no resize)
            frame_proc = frame

            # Detection (uses shared Detector singleton)
            detections = source_tracker.update(frame_proc, detector.detect(frame_proc))
            raw_ids = set()
            for detection in detections:
                raw_id = detection.get("track_id")
                if raw_id is None:
                    continue
                raw_ids.add(raw_id)
                detection["raw_track_id"] = raw_id
                detection["track_id"] = identity_resolver.resolve(raw_id, detection["bbox"])
            identity_resolver.retire_missing(raw_ids)

            # ORB fence tracking
            orb_fence = fence_checker.track_fence(frame_proc)

            # Fence check

            poses = pose_detector.estimate(frame_proc, detections) if frame_idx % 5 == 0 else {}
            alerts = fence_checker.update(detections, poses)

            # Filter alerts by configured alert classes (live config read)
            try:
                db = SessionLocal()
                cfg = db.query(Config).filter(Config.id == 1).first()
                if cfg and cfg.alert_classes:
                    classes = set(json.loads(cfg.alert_classes))
                    alerts = [a for a in alerts if a["class_name"] in classes]
                db.close()
            except Exception:
                pass

            track_states = fence_checker.get_track_states()
            fence_pixels = orb_fence if orb_fence else fence_checker.get_fence_pixels()
            track_boxes = {track["track_id"]: track["bbox"] for track in track_states}

            # Keep image and tracking metadata together for adaptive sampling.
            with ring_buffer_lock:
                ring_buffer.append((time.time(), frame_proc.copy(), track_boxes))

            # Handle alert clip writing
            if alerts and clip_writer is None:
                pre_sec = 5.0
                now = time.time()
                pre_frames = []
                for ts, frm, _ in ring_buffer:
                    if ts >= now - pre_sec:
                        pre_frames.append(frm)

                clip_name = f"alert_{source_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}.mp4"
                clip_path = str(CLIPS_DIR / clip_name)
                fourcc = cv2.VideoWriter_fourcc(*"avc1")
                clip_writer = cv2.VideoWriter(clip_path, fourcc, fps, (w, h))

                if clip_writer.isOpened():
                    for pf in pre_frames:
                        clip_writer.write(pf)
                    clip_frames_remaining = int(10 * fps) - 1

            if clip_writer is not None:
                if clip_frames_remaining > 0:
                    clip_writer.write(frame_proc)
                    clip_frames_remaining -= 1
                else:
                    clip_writer.release()
                    clip_writer = None
                    result_queue.put({
                        "source_id": source_id,
                        "type": "clip_ready",
                        "clip_path": clip_path,
                        "alert_class": alerts[-1]["class_name"] if alerts else "unknown",
                    })

            # Save snapshot for each alert
            for alert in alerts:
                ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
                snap_name = f"alert_{source_id}_{ts}.jpg"
                snap_path = str(SNAPSHOTS_DIR / snap_name)
                cv2.imwrite(snap_path, frame_proc, [cv2.IMWRITE_JPEG_QUALITY, 85])
                alert["snapshot_path"] = snap_path
                alert["trigger_time"] = time.time()
                alert["alert_key"] = uuid4().hex
                alert["fence_points"] = fence_pixels

            # Encode JPEG
            jpg_b64 = encode_frame(frame_proc)

            # Send to main thread
            result_queue.put({
                "source_id": source_id,
                "type": "frame",
                "frame_index": frame_idx,
                "width": w,
                "height": h,
                "image": jpg_b64,
                "detections": detections,
                "tracks": track_states,
                "fence_pixels": fence_pixels,
                "orb_tracking": fence_checker.orb_active,
                "alerts": alerts,
            })

            time.sleep(1.0 / 25.0)

    except Exception:
        result_queue.put({"source_id": source_id, "type": "error", "error": traceback.format_exc()})
    finally:
        if clip_writer is not None:
            clip_writer.release()
        try:
            cap.release()
        except Exception:
            pass
        result_queue.put({"source_id": source_id, "type": "stopped"})

# ---------------------------------------------------------------------------
# Stream Manager (main thread)
# ---------------------------------------------------------------------------

class StreamManager:
    """Manages multiple video sources with shared-model threads."""

    def __init__(self):
        self._sources: dict[str, dict] = {}
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self.BROADCAST_INTERVAL = 1.0 / 30.0

        # Pre-load detector on startup (once, shared by all threads)
        self.detector = Detector()
        self.pose_detector = PoseDetector()
        if self.detector.is_ready:
            logger.info("YOLO model pre-loaded and ready (shared)")
        else:
            logger.warning("YOLO model not ready - detection will fail")

    def add_source(self, source_type: str, source_arg: str,
                   fence_checker: Optional[FenceChecker] = None) -> str:
        source_id = uuid4().hex[:12]
        queue: Queue = Queue(maxsize=500)
        stop_event = Event()
        ring_buffer: deque = deque(maxlen=375)
        ring_buffer_lock = Lock()

        if fence_checker is None:
            fence_checker = FenceChecker()

        source_tracker = SourceTracker(source_id, 25.0)

        thread = Thread(
            target=_source_worker,
            args=(source_id, source_type, source_arg, queue, stop_event,
                  self.detector, self.pose_detector, source_tracker, fence_checker, ring_buffer, ring_buffer_lock),
            daemon=True,
        )
        thread.start()

        self._sources[source_id] = {
            "type": source_type,
            "arg": source_arg,
            "thread": thread,
            "queue": queue,
            "stop_event": stop_event,
            "fence_checker": fence_checker,
            "source_tracker": source_tracker,
            "ring_buffer": ring_buffer,
            "ring_buffer_lock": ring_buffer_lock,
            "ready": False,
            "fps": 25.0,
        }

        if not self._running:
            self._start_consume_loop()

        logger.info(f"Source added: {source_id} ({source_type}: {source_arg})")
        return source_id

    def remove_source(self, source_id: str) -> bool:
        src = self._sources.pop(source_id, None)
        if src is None:
            return False
        src["stop_event"].set()
        src["thread"].join(timeout=5)
        logger.info(f"Source removed: {source_id}")
        return True

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        for sid in list(self._sources.keys()):
            self.remove_source(sid)
        logger.info("All sources stopped")

    def get_sources(self) -> list[dict]:
        return [
            {
                "source_id": sid,
                "type": s["type"],
                "arg": s["arg"],
                "ready": s["ready"],
                "fps": s["fps"],
            }
            for sid, s in self._sources.items()
        ]

    def get_source_ids(self) -> list[str]:
        return list(self._sources.keys())

    @property
    def is_running(self) -> bool:
        return self._running and len(self._sources) > 0

    def get_fence_checker(self, source_id: str) -> Optional[FenceChecker]:
        src = self._sources.get(source_id)
        return src["fence_checker"] if src else None

    # ---- Main consume loop ----

    def _start_consume_loop(self) -> None:
        self._running = True
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._consume_loop())

    async def _consume_loop(self) -> None:
        logger.info("Consume loop started")
        error_count = 0

        while self._running:
            try:
                for sid, src in list(self._sources.items()):
                    q: Queue = src["queue"]
                    while True:
                        try:
                            msg = q.get_nowait()
                        except Empty:
                            break

                        msg_type = msg.get("type")

                        if msg_type == "ready":
                            src["ready"] = True
                            src["fps"] = msg.get("fps", 25.0)
                            logger.info(f"Source {sid} ready @ {src['fps']}fps")

                        elif msg_type == "frame":
                            await sse_broadcaster.broadcast({
                                "type": "frame",
                                "source_id": sid,
                                "width": msg["width"],
                                "height": msg["height"],
                                "detections": msg["detections"],
                                "tracks": msg["tracks"],
                                "fence_pixels": msg["fence_pixels"],
                                "orb_tracking": msg["orb_tracking"],
                                "alerts": msg["alerts"],
                            })

                            await ws_broadcaster.broadcast_to_source(sid, msg)

                            for alert in msg["alerts"]:
                                trigger_time = alert.pop("trigger_time", time.time())
                                asyncio.create_task(
                                    self._finalize_alert(
                                        sid, alert, src["ring_buffer"],
                                        src["ring_buffer_lock"], trigger_time
                                    )
                                )

                        elif msg_type == "clip_ready":
                            await self._attach_clip(sid, msg["clip_path"])

                        elif msg_type == "error":
                            logger.error(f"Source {sid} error: {msg.get('error', '')[:200]}")

                        elif msg_type == "stopped":
                            logger.info(f"Source {sid} stopped")
                            src["ready"] = False

                error_count = 0

            except asyncio.CancelledError:
                break
            except Exception:
                error_count += 1
                logger.error(f"Consume error (#{error_count}): {traceback.format_exc()}")
                if error_count > 20:
                    self._running = False
                    break

            await asyncio.sleep(self.BROADCAST_INTERVAL)

        logger.info("Consume loop exited")

    async def _finalize_alert(
        self, source_id: str, alert: dict, ring_buffer: deque,
        ring_buffer_lock: Lock, trigger_time: float
    ) -> None:
        """Wait for the post-alert frame, then analyze and persist the alert."""
        await asyncio.sleep(max(0.0, trigger_time + 10.0 - time.time()))
        with ring_buffer_lock:
            frames, boxes = select_adaptive_frames(
                list(ring_buffer), trigger_time, alert.get("track_id"), alert["bbox"]
            )
        alert["vllm_analysis"] = ""
        alert["vllm_risk_level"] = ""
        alert["vllm_is_destructive"] = None
        if len(frames) == 3:
            db = SessionLocal()
            try:
                config = db.query(Config).filter(Config.id == 1).first()
                if config:
                    crops = [crop_alert_frames([frame], box, padding=max(16, int((box[2] - box[0]) * 0.4)))[0]
                             for frame, box in zip(frames, boxes)]
                    panoramas = annotate_panorama_frames(
                        frames, boxes, alert.get("fence_points", []), alert.get("track_id", 0)
                    )
                    evidence_frames = compose_context_frames(panoramas, crops) if len(crops) == 3 else panoramas
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(
                        None, analyze_frames, config, evidence_frames, alert.get("behavior_candidate", "normal")
                    )
                    alert["vllm_analysis"] = result["analysis"]
                    alert["vllm_risk_level"] = result["risk_level"]
                    alert["vllm_is_destructive"] = result["is_destructive"]
            except Exception as exc:
                logger.warning("vLLM alert analysis failed: %s", exc)
            finally:
                db.close()
        await self._handle_alert(source_id, alert)

    async def _handle_alert(self, source_id: str, alert: dict) -> None:
        bbox_json = json.dumps(alert["bbox"])
        timestamp = datetime.utcnow()

        snapshot_path = alert.get("snapshot_path", "")

        db = SessionLocal()
        try:
            record = Alert(
                class_name=alert["class_name"],
                confidence=alert["confidence"],
                bbox=bbox_json,
                timestamp=timestamp,
                video_source=source_id,
                snapshot_path=str(snapshot_path),
                vllm_analysis=alert.get("vllm_analysis") or None,
                vllm_risk_level=alert.get("vllm_risk_level") or None,
                vllm_is_destructive=alert.get("vllm_is_destructive"),
            )
            db.add(record)
            db.commit()
            alert_ready = {
                "type": "alert_ready", "id": record.id, "alert_key": alert.get("alert_key", ""),
                "class_name": record.class_name, "confidence": record.confidence,
                "bbox": alert["bbox"], "track_id": alert.get("track_id"),
                "timestamp": record.timestamp.isoformat(), "video_source": source_id,
                "snapshot_path": record.snapshot_path, "clip_path": record.clip_path,
                "status": record.status or "pending", "vllm_analysis": record.vllm_analysis,
                "vllm_risk_level": record.vllm_risk_level,
                "vllm_is_destructive": record.vllm_is_destructive,
            }
            await ws_broadcaster.broadcast_to_source(source_id, alert_ready)
        except Exception as e:
            logger.error(f"Failed to save alert: {e}")
        finally:
            db.close()

        asyncio.create_task(send_alert_notification(alert))

    async def _attach_clip(self, source_id: str, clip_path: str) -> None:
        db = SessionLocal()
        try:
            latest = (
                db.query(Alert)
                .filter(Alert.video_source == source_id)
                .order_by(Alert.timestamp.desc())
                .first()
            )
            if latest:
                latest.clip_path = clip_path
                db.commit()
                logger.info(f"Clip attached to alert #{latest.id}")
        except Exception as e:
            logger.error(f"Failed to attach clip: {e}")
        finally:
            db.close()

stream_manager = StreamManager()
