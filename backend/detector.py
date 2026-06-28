"""YOLO detector --- singleton + GPU/CPU + local model support"""
import threading
import logging
import numpy as np
from pathlib import Path
from ultralytics import YOLO
from config import MODEL_PATH, MODEL_NAME, DEVICE, DETECTION_CLASSES, CONFIDENCE_THRESHOLD, IOU_THRESHOLD

logger = logging.getLogger(__name__)


class Detector:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init = False
        return cls._instance

    def __init__(self):
        if self._init:
            return

        local_path = Path(MODEL_PATH)
        if local_path.exists():
            model_src = str(local_path)
            logger.info(f"Loading local model: {model_src}")
        else:
            model_src = f"{MODEL_NAME}.pt"
            logger.warning(
                f"Model not found at {MODEL_PATH}, "
                f"ultralytics will try to download '{model_src}'. "
                f"Place your .pt file in backend/models/ to skip download."
            )

        self.model = None
        self._load_model(model_src)
        self._init = True

    def _load_model(self, model_src: str) -> None:
        """Try loading on GPU first, then CPU. Raise on total failure."""
        for device in [DEVICE, "cpu"]:
            try:
                logger.info(f"Trying {model_src} on {device}...")
                self.model = YOLO(model_src)
                self.model.to(device)
                logger.info(f"Detector ready on {device}")
                return
            except Exception as e:
                logger.warning(f"Failed on {device}: {e}")
                self.model = None
                continue

        # All attempts failed — create a dummy detector that returns empty results
        logger.critical(
            f"Cannot load model '{model_src}'. "
            f"Place your .pt file at {MODEL_PATH} and restart."
        )
        self.model = None

    @property
    def is_ready(self) -> bool:
        return self.model is not None

    def detect(self, frame: np.ndarray) -> list[dict]:
        """Safe detection with ByteTrack: returns empty list if model not loaded."""
        if self.model is None:
            return []

        try:
            results = self.model.track(
                frame,
                persist=True,
                tracker="bytetrack.yaml",
                conf=CONFIDENCE_THRESHOLD,
                iou=IOU_THRESHOLD,
                verbose=False,
            )
        except Exception:
            return []

        detections = []
        if results[0].boxes is not None:
            boxes_data = results[0].boxes
            for i in range(len(boxes_data.cls)):
                cls_id = int(boxes_data.cls[i])
                if cls_id in DETECTION_CLASSES:
                    x1, y1, x2, y2 = boxes_data.xyxy[i].tolist()
                    track_id = int(boxes_data.id[i]) if boxes_data.id is not None else None
                    detections.append({
                        "class_id": cls_id,
                        "class_name": self.model.names[cls_id],
                        "confidence": float(boxes_data.conf[i]),
                        "bbox": [int(x1), int(y1), int(x2), int(y2)],
                        "track_id": track_id,
                    })
        return detections
