"""WebSocket streaming: JPEG frames + detection data, per-source routing"""
import asyncio
import base64
import json
import logging
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

JPEG_QUALITY = 75
MAX_CLIENTS_PER_SOURCE = 5


class WSBroadcaster:
    """Fan-out JPEG frames + detection data per source."""

    def __init__(self):
        # source_id -> {client_id: WebSocket}
        self._sources: dict[str, dict[int, WebSocket]] = {}
        self._lock: Optional[asyncio.Lock] = None  # lazy init for Python 3.9 compat
        self._next_id = 0

    def _ensure_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def subscribe(self, source_id: str, ws: WebSocket) -> int:
        await ws.accept()
        async with self._ensure_lock():
            cid = self._next_id
            self._next_id += 1
            if source_id not in self._sources:
                self._sources[source_id] = {}
            self._sources[source_id][cid] = ws
        logger.info(f"WS client #{cid} -> source={source_id} ({len(self._sources[source_id])} total)")
        return cid

    async def unsubscribe(self, source_id: str, cid: int) -> None:
        async with self._ensure_lock():
            if source_id in self._sources:
                self._sources[source_id].pop(cid, None)
        logger.info(f"WS client #{cid} disconnected from {source_id}")

    async def broadcast_to_source(self, source_id: str, data: dict) -> None:
        """Send JSON message to all clients subscribed to a specific source."""
        payload = json.dumps(data, ensure_ascii=False)
        async with self._ensure_lock():
            clients = self._sources.get(source_id, {})
            dead = []
            for cid, ws in clients.items():
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(cid)
            for cid in dead:
                clients.pop(cid, None)
                logger.warning(f"WS client #{cid} dropped from {source_id}")

    def source_client_count(self, source_id: str) -> int:
        return len(self._sources.get(source_id, {}))

    @property
    def client_count(self) -> int:
        return sum(len(c) for c in self._sources.values())


ws_broadcaster = WSBroadcaster()


@router.websocket("/ws/{source_id}")
async def websocket_endpoint(ws: WebSocket, source_id: str):
    cid = await ws_broadcaster.subscribe(source_id, ws)
    try:
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=30.0)
                if data == "ping":
                    await ws.send_text("pong")
            except asyncio.TimeoutError:
                await ws.send_text("ping")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"WS client #{cid} source={source_id} error: {e}")
    finally:
        await ws_broadcaster.unsubscribe(source_id, cid)


def encode_frame(frame: np.ndarray) -> str:
    """Encode BGR numpy frame to base64 JPEG string."""
    _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    return base64.b64encode(jpeg).decode("ascii")