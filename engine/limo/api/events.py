import asyncio
import queue
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from limo.events.bus import EventBus

POLL_S = 0.1


def events_router(bus: EventBus, heartbeat_s: float) -> APIRouter:
    router = APIRouter()

    @router.get("/api/events")
    async def stream_events(request: Request) -> StreamingResponse:
        return StreamingResponse(
            _stream(bus, request, heartbeat_s),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    return router


async def _stream(bus: EventBus, request: Request, heartbeat_s: float) -> AsyncIterator[str]:
    sub = bus.subscribe()
    try:
        yield ": connected\n\n"
        idle = 0.0
        while not await request.is_disconnected():
            try:
                event = sub.get_nowait()
            except queue.Empty:
                await asyncio.sleep(POLL_S)
                idle += POLL_S
                if idle >= heartbeat_s:
                    idle = 0.0
                    yield ": ping\n\n"
                continue
            idle = 0.0
            yield event.to_sse()
    finally:
        bus.unsubscribe(sub)
