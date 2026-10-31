"""SSE endpoint — streams tool invocation events.

GET /api/events/tools → text/event-stream
Each event: id: {n}\ndata: {json}\n\n
Keepalive: `: ping` every 15 s.
Supports Last-Event-ID for reconnect deduplication.

Stream logic lives in factory.mcp_utils.tool_event_stream — this module
is a pure transport shell that wires the route and serialises to SSE wire format.
"""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

# CORS handled globally by Starlette CORSMiddleware (factory.mcp_utils.cors).
_STREAM_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def register_events_sse_routes(app) -> None:
    """Register SSE tool-stream routes on a FastAPI app instance."""
    from starlette.requests import Request
    from starlette.responses import StreamingResponse
    from starlette.routing import Route
    from factory.mcp_utils.interface import tool_invocation_stream, _SENTINEL_PING

    async def tools_stream(request: Request) -> StreamingResponse:
        last_event_id = request.headers.get("last-event-id")
        try:
            last_seen = int(last_event_id) if last_event_id else 0
        except (ValueError, TypeError):
            last_seen = 0

        async def event_stream():
            counter = 0
            try:
                async for item in tool_invocation_stream(last_seen=last_seen):
                    if item is _SENTINEL_PING:
                        yield ": ping\n\n"
                    else:
                        counter += 1
                        yield f"id: {counter}\ndata: {json.dumps(item)}\n\n"
            except Exception:
                pass

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers=_STREAM_HEADERS,
        )

    app.routes.extend([
        Route("/api/events/tools", tools_stream, methods=["GET"]),
    ])
