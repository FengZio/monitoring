"""SSE endpoint - replaces WebSocket for detection data"""
import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from sse_manager import sse_broadcaster

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["sse"])


@router.get("/stream")
async def sse_stream(request: Request):
    """Server-Sent Events stream of detection data."""

    cid, queue = await sse_broadcaster.subscribe()

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"event: frame\ndata: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            await sse_broadcaster.unsubscribe(cid)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
