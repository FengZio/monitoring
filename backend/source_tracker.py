"""Per-source BoT-SORT tracker with optional ReID appearance matching."""
import logging
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import yaml

logger = logging.getLogger(__name__)


class _DetectionResults:
    def __init__(self, detections):
        self.conf = np.asarray([item["confidence"] for item in detections], dtype=np.float32)
        self.cls = np.asarray([item["class_id"] for item in detections], dtype=np.float32)
        xyxy = np.asarray([item["bbox"] for item in detections], dtype=np.float32)
        self.xywh = np.column_stack(((xyxy[:, 0] + xyxy[:, 2]) / 2, (xyxy[:, 1] + xyxy[:, 3]) / 2,
                                      xyxy[:, 2] - xyxy[:, 0], xyxy[:, 3] - xyxy[:, 1])) if len(xyxy) else np.empty((0, 4), dtype=np.float32)


class SourceTracker:
    def __init__(self, source_id: str, fps: float):
        self.source_id = source_id
        self.tracker = None
        self._fallback_tracks = {}
        self._next_fallback_id = 1
        try:
            from ultralytics.trackers.bot_sort import BOTSORT
            config_path = Path(__file__).resolve().parent / "botsort_reid.yaml"
            config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            self.tracker = BOTSORT(SimpleNamespace(**config), frame_rate=max(1, int(fps)))
            logger.info("BoT-SORT ReID ready for source=%s", source_id)
        except Exception as exc:
            logger.warning("BoT-SORT ReID unavailable for source=%s; detections stay untracked: %s", source_id, exc)

    def update(self, frame, detections):
        if self.tracker is None or not detections:
            return self._assign_fallback_ids(detections)
        try:
            tracks = self.tracker.update(_DetectionResults(detections), frame)
            for row in tracks:
                detection_index = int(row[-1])
                if 0 <= detection_index < len(detections):
                    detections[detection_index]["track_id"] = int(row[4])
            return self._assign_fallback_ids(detections)
        except Exception as exc:
            logger.warning("BoT-SORT update failed for source=%s: %s", self.source_id, exc)
            return self._assign_fallback_ids(detections)

    @staticmethod
    def _iou(a, b):
        x1, y1 = max(a[0], b[0]), max(a[1], b[1])
        x2, y2 = min(a[2], b[2]), min(a[3], b[3])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        union = max(1, (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter)
        return inter / union

    def _assign_fallback_ids(self, detections):
        used = set()
        for detection in detections:
            if detection.get("track_id") is not None:
                continue
            candidates = [(self._iou(detection["bbox"], box), track_id) for track_id, box in self._fallback_tracks.items() if track_id not in used]
            score, track_id = max(candidates) if candidates else (0, None)
            if score < 0.3:
                track_id = -self._next_fallback_id
                self._next_fallback_id += 1
            detection["track_id"] = track_id
            used.add(track_id)
        self._fallback_tracks = {detection["track_id"]: detection["bbox"] for detection in detections}
        return detections
