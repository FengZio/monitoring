"""Fence checker with ORB auto-tracking"""
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

from config import ORB_TRACK_INTERVAL

logger = logging.getLogger(__name__)


@dataclass
class TrackedObject:
    track_id: int
    class_name: str
    bbox: list[int]
    inside_fence: bool = False
    was_alerted: bool = False
    last_seen: float = field(default_factory=time.time)


class FenceChecker:
    def __init__(self):
        self._fence_points: list[tuple[float, float]] = []
        self._fence_mode: str = 'restricted'  # restricted | enclosure
        self._tracks: dict[int, TrackedObject] = {}
        self._next_id = 0
        self._max_miss_sec = 10

        # ORB tracking
        self._orb = cv2.ORB_create(nfeatures=1500)
        self._bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        self._ref_gray: Optional[np.ndarray] = None
        self._ref_kp: Optional[tuple] = None
        self._ref_des: Optional[np.ndarray] = None
        self._ref_fence: list[tuple[float, float]] = []
        self._auto_tracking = False
        self._track_skip = 0

    # ==================== Fence ====================

    def set_fence(self, points: list[list[float]], mode: str = "restricted") -> None:
        self._fence_points = [(p[0], p[1]) for p in points if len(p) >= 2]
        self._fence_mode = mode
        self._tracks.clear()

    @property
    def has_fence(self) -> bool:
        return len(self._fence_points) >= 3

    def get_fence_pixels(self) -> list[list[float]]:
        return [[x, y] for x, y in self._fence_points]

    # ==================== ORB auto-tracking ====================

    def capture_reference(self, frame: np.ndarray) -> None:
        if frame is None:
            return
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        kp, des = self._orb.detectAndCompute(gray, None)
        if des is None or len(kp) < 15:
            logger.warning("ORB: not enough features")
            return
        self._ref_gray = gray.copy()
        self._ref_kp = kp
        self._ref_des = des
        self._ref_fence = list(self._fence_points)
        self._auto_tracking = True
        self._track_skip = 0
        logger.info(f"ORB ref: {len(kp)} keypoints")

    def track_fence(self, frame: np.ndarray) -> Optional[list[list[float]]]:
        if not self._auto_tracking or self._ref_gray is None:
            return None
        if self._ref_kp is None or self._ref_des is None:
            return None
        if not self._fence_points:
            return None

        self._track_skip += 1
        if self._track_skip % ORB_TRACK_INTERVAL != 0:
            return self.get_fence_pixels()

        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            kp, des = self._orb.detectAndCompute(gray, None)
            if des is None or len(kp) < 10:
                return self.get_fence_pixels()

            matches = self._bf.match(self._ref_des, des)
            matches = sorted(matches, key=lambda m: m.distance)

            if len(matches) < 8:
                return self.get_fence_pixels()

            src_pts = np.float32([self._ref_kp[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            if M is None:
                return self.get_fence_pixels()

            fence_pts = np.float32(self._ref_fence).reshape(-1, 1, 2)
            projected = cv2.perspectiveTransform(fence_pts, M)
            self._fence_points = [(float(p[0][0]), float(p[0][1])) for p in projected]

            return self.get_fence_pixels()
        except Exception as e:
            logger.warning(f"ORB tracking error: {e}")
            return self.get_fence_pixels()

    @property
    def orb_active(self) -> bool:
        return self._auto_tracking

    def stop_orb(self) -> None:
        self._auto_tracking = False
        self._ref_gray = None
        self._ref_kp = None
        self._ref_des = None

    # ==================== Foot point ====================

    def _foot_point(self, bbox: list[int]) -> tuple[float, float]:
        x1, _, x2, y2 = bbox
        return ((x1 + x2) / 2.0, float(y2))

    # ==================== Point-in-polygon ====================

    @staticmethod
    def point_in_polygon(px: float, py: float, polygon: list[tuple[float, float]]) -> bool:
        n = len(polygon)
        if n < 3:
            return False
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    def update(self, detections: list[dict]) -> list[dict]:
        """Update tracks using ByteTrack assigned track_id (no IOU matching)."""
        now = time.time()
        alerts: list[dict] = []
        seen_ids: set[int] = set()

        for det in detections:
            bt_track_id = det.get("track_id")
            check_pt = self._foot_point(det["bbox"])
            currently_inside = (
                self.has_fence
                and self.point_in_polygon(check_pt[0], check_pt[1], self._fence_points)
            )

            if bt_track_id is not None:
                seen_ids.add(bt_track_id)
                tobj = self._tracks.get(bt_track_id)

                if tobj is not None:
                    # Existing track: check fence transition
                    was_inside = tobj.inside_fence
                    tobj.bbox = det["bbox"]
                    tobj.last_seen = now

                    trigger = False
                    if self._fence_mode == "restricted":
                        trigger = currently_inside and not was_inside and not tobj.was_alerted
                    else:  # enclosure
                        trigger = not currently_inside and was_inside and not tobj.was_alerted

                    if trigger:
                        tobj.inside_fence = currently_inside
                        tobj.was_alerted = True
                        alerts.append({
                            "track_id": bt_track_id,
                            "class_name": tobj.class_name,
                            "confidence": det["confidence"],
                            "bbox": det["bbox"],
                        })
                    elif not currently_inside:
                        tobj.inside_fence = False
                        tobj.was_alerted = False
                    else:
                        tobj.inside_fence = currently_inside
                else:
                    # New track from ByteTrack
                    self._tracks[bt_track_id] = TrackedObject(
                        track_id=bt_track_id,
                        class_name=det["class_name"],
                        bbox=det["bbox"],
                        inside_fence=currently_inside,
                        was_alerted=currently_inside,
                        last_seen=now,
                    )
            else:
                # No ByteTrack ID: assign a local id as fallback
                tid = self._next_id
                self._next_id += 1
                seen_ids.add(tid)
                self._tracks[tid] = TrackedObject(
                    track_id=tid,
                    class_name=det["class_name"],
                    bbox=det["bbox"],
                    inside_fence=currently_inside,
                    was_alerted=currently_inside,
                    last_seen=now,
                )

        # Clean up stale tracks (not seen in this frame and expired)
        self._tracks = {
            tid: t for tid, t in self._tracks.items()
            if tid in seen_ids or (now - t.last_seen < self._max_miss_sec)
        }
        return alerts

    def get_track_states(self) -> list[dict]:
        return [
            {"track_id": t.track_id, "class_name": t.class_name,
             "bbox": t.bbox, "inside_fence": t.inside_fence}
            for t in self._tracks.values()
        ]