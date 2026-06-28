"""FastAPI entry"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import UPLOADS_DIR, SNAPSHOTS_DIR, BASE_DIR
from database import init_db
from stream_bridge import stream_manager
from routes import video, fence, alerts, config_route
from routes.ws_stream import router as ws_router
from routes.stats import router as stats_router
from routes.sse import router as sse_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

init_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / Shutdown."""
    logger.info("Starting e-fence monitor v3 (multi-source + ByteTrack)...")
    yield
    logger.info("Shutting down...")
    stream_manager.stop()
    logger.info("Shutdown complete")


app = FastAPI(title="electron fence monitor", version="3.0.0", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/snapshots", StaticFiles(directory=str(SNAPSHOTS_DIR)), name="snapshots")

# Routes
app.include_router(video.router)
app.include_router(fence.router)
app.include_router(alerts.router)
app.include_router(config_route.router)
app.include_router(stats_router)
app.include_router(sse_router)
app.include_router(ws_router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "streaming": stream_manager.is_running,
        "sources": stream_manager.get_source_ids(),
        "mode": "multiprocess+bytetrack",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
