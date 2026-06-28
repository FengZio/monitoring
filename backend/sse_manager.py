"""SSE Pub/Sub broadcaster — one Queue per connected client"""
import asyncio
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SSEBroadcaster:
    """Fan-out detection data to all connected SSE clients."""

    def __init__(self):
        self._queues: dict[int, asyncio.Queue] = {}
        self._lock: Optional[asyncio.Lock] = None  # lazy init for Python 3.9 compat
        self._next_id = 0
        self._frame_index = 0

    def _ensure_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def subscribe(self) -> tuple[int, asyncio.Queue]:
        """Register a new SSE client. Returns (client_id, queue)."""
        q: asyncio.Queue = asyncio.Queue(maxsize=120)
        async with self._ensure_lock():
            cid = self._next_id
            self._next_id += 1
            self._queues[cid] = q
        logger.info(f"SSE client #{cid} subscribed ({len(self._queues)} total)")
        return cid, q

    async def unsubscribe(self, client_id: int) -> None:
        """Remove a disconnected SSE client."""
        async with self._ensure_lock():
            self._queues.pop(client_id, None)
        logger.info(f"SSE client #{client_id} unsubscribed ({len(self._queues)} remaining)")

    async def broadcast(self, data: dict) -> None:
        """Push data to all connected SSE clients. Slow clients are dropped."""
        data["frame_index"] = self._frame_index
        self._frame_index += 1
        payload = json.dumps(data, ensure_ascii=False)

        async with self._ensure_lock():
            dead = []
            for cid, q in self._queues.items():
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    dead.append(cid)
            for cid in dead:
                self._queues.pop(cid, None)
                logger.warning(f"SSE client #{cid} dropped (queue full)")

    @property
    def client_count(self) -> int:
        return len(self._queues)

    @property
    def frame_index(self) -> int:
        return self._frame_index


# ---- singleton ----
sse_broadcaster = SSEBroadcaster()