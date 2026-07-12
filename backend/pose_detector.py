"""Low-frequency YOLO pose estimation for tracked people."""
import logging
from pathlib import Path

from ultralytics import YOLO

from config import DEVICE, POSE_MODEL_PATH

logger = logging.getLogger(__name__)


class PoseDetector:
    def __init__(self):
        self.model = None
        self._inference_count = 0
        try:
            source = POSE_MODEL_PATH if Path(POSE_MODEL_PATH).exists() else "yolo11n-pose.pt"
            self.model = YOLO(source)
            self.model.to(DEVICE)
            logger.info("Pose detector ready: %s", source)
        except Exception as exc:
            logger.warning("Pose detector unavailable, using trajectory fallback: %s", exc)

    def estimate(self, frame, detections: list[dict]) -> dict[int, dict]:
        if self.model is None:
            return {}
        poses = {}
        person_count = 0
        for detection in detections:
            if detection["class_name"] != "person" or detection.get("track_id") is None:
                continue
            person_count += 1
            x1, y1, x2, y2 = detection["bbox"]
            crop = frame[max(0, y1):max(0, y2), max(0, x1):max(0, x2)]
            if crop.size == 0:
                continue
            try:
                result = self.model(crop, verbose=False)[0]
                if result.keypoints is None or len(result.keypoints.xy) == 0:
                    continue
                xy = result.keypoints.xy[0].cpu().tolist()
                confidence_data = result.keypoints.conf
                confidence = confidence_data[0].cpu().tolist() if confidence_data is not None else [1.0] * len(xy)
                poses[detection["track_id"]] = {
                    index: [point[0] + x1, point[1] + y1, confidence[index]]
                    for index, point in enumerate(xy)
                }
            except Exception as exc:
                logger.warning("Pose estimation skipped: %s", exc)
        self._inference_count += 1
        if self._inference_count % 20 == 1:
            logger.info("Pose inference: person_rois=%d keypoint_sets=%d", person_count, len(poses))
        return poses
