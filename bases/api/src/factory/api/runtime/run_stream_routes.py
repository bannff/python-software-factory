"""Per-run SSE endpoint — tails the event_bus filtered by run_id.

GET /api/stream/run/{run_id}

Streams raw event_bus payloads tagged with the given run_id as plain
SSE lines (``data: <json>\\n\\n``).  No AG-UI envelope — this is the
telemetry/monitoring channel for background spawn tracking (P2b) and
live debugging of P1a spawn runs.

Design notes:
- Runs indefinitely until the client disconnects (no chat_done sentinel).
- ``request.is_disconnected()`` is polled inside the generator loop so the
  connection is released cleanly without waiting for the next event.
- ``_extract_run_id`` is a local copy of the same logic from
  ``ag_ui_chat_stream._event_run_id`` to avoid sibling-module cross-imports
  inside the base (bases are pure transport shells; sibling imports are
  allowed but keeping the tiny helper inline avoids coupling two independent
  transport modules together).
- bd:python-factory-tko13
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# CORS handled globally by Starlette CORSMiddleware (factory.mcp_utils.cors).
_STREAM_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
    "Content-Encoding": "identity",
}


def _extract_run_id(evt: dict[str, Any]) -> str | None:
    """Extract a run_id-like value from an event_bus payload.

    Mirrors ``ag_ui_chat_stream._event_run_id`` — local copy to avoid
    coupling this transport module to a sibling module.
    """
    if not isinstance(evt, dict):
        return None
    rid = evt.get("workflow_run_id") or evt.get("run_id")
    if rid:
        return str(rid)
    payload = evt.get("payload")
    if isinstance(payload, dict):
        rid = payload.get("workflow_run_id") or payload.get("run_id")
        if rid:
            return str(rid)
    return None


def register_run_stream_routes(app) -> None:
    """Register the per-run SSE stream route on a FastAPI app instance."""
    from starlette.requests import Request
    from starlette.responses import StreamingResponse
    from starlette.routing import Route

    async def run_stream(request: Request) -> StreamingResponse:
        run_id: str = request.path_params["run_id"]

        async def _stream():
            from factory.mcp_utils.interface import event_bus
            try:
                async for raw in event_bus.subscribe():
                    if await request.is_disconnected():
                        break
                    if not isinstance(raw, dict):
                        continue
                    rid = _extract_run_id(raw)
                    if rid != run_id:
                        continue
                    yield f"data: {json.dumps(raw)}\n\n"
            except asyncio.CancelledError:
                pass
            except Exception:  # noqa: BLE001 — defence in depth
                logger.debug("run_stream drain error", exc_info=True)

        return StreamingResponse(
            _stream(),
            media_type="text/event-stream",
            headers=_STREAM_HEADERS,
        )

    app.routes.extend([
        Route("/api/stream/run/{run_id}", run_stream, methods=["GET"]),
    ])


__all__ = ["register_run_stream_routes"]
