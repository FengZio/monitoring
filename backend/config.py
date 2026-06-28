"""global config"""
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"
SNAPSHOTS_DIR = UPLOADS_DIR / "snapshots"
MODELS_DIR = BASE_DIR / "models"
DB_PATH = BASE_DIR / "monitoring.db"

# ---- auto-detect device ----
try:
    import torch
    if torch.cuda.is_available():
        DEVICE = "cuda"
        logger.info("GPU detected, using CUDA")
    else:
        DEVICE = "cpu"
        logger.warning("No GPU found, using CPU")
except Exception:
    DEVICE = "cpu"
    logger.warning("torch not available, using CPU")

# ---- model config ----
MODEL_NAME = "yolov8n"
MODEL_PATH = str(MODELS_DIR / f"{MODEL_NAME}.pt")

DETECTION_CLASSES = {0, 1, 2, 3, 5, 7}    # person, bicycle, car, motorcycle, bus, truck
CONFIDENCE_THRESHOLD = 0.4
IOU_THRESHOLD = 0.45
FRAME_WIDTH = 1280        # display and detection resolution (1080p)
ORB_TRACK_INTERVAL =5      # run ORB every N frames (1=every frame, 5=balanced)

# ---- ensure dirs ----
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)



