"""Async generator for tool invocation and activity events.

Used by the API base SSE endpoint. Extracted here so the base stays a pure
transport shell (no brick-specific logic).

Merges two sources into one stream:
- graph poll: ToolInvocation entities (cross-process, production)
- event_bus: live events bridged from the events brick (swarm, game, etc.)
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

from .registry import get_service
from .poll_noise import POLL_NOISE as _POLL_NOISE
from . import event_bus

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 1.0
_KEEPALIVE_INTERVAL = 15.0

_SENTINEL_PING = object()


def _normalize_event(props: dict[str, Any]) -> dict[str, Any] | None:
    """Map ToolInvocation entity properties to SSE event schema.

    Returns None for poll-noise events that should be filtered out.
    """
    tool = props.get("tool") or props.get("tool_name", "unknown")
    if tool in _POLL_NOISE:
        return None
    ts = props.get("ts") or props.get("created_at")
    if isinstance(ts, str):
        from datetime import datetime
        try:
            ts = datetime.fromisoformat(ts).timestamp()
        except (ValueError, TypeError):
            ts = time.time()
    evt: dict[str, Any] = {
        "tool": tool,
        "brick": props.get("brick") or props.get("brick_name", "unknown"),
        "success": props.get("success", True),
        "latency_ms": props.get("latency_ms", 0),
        "ts": ts or time.time(),
    }
    session_id = props.get("session_id")
    workflow_run_id = props.get("workflow_run_id") or props.get("run_id")
    if session_id is not None:
        evt["session_id"] = session_id
    if workflow_run_id is not None:
        evt["workflow_run_id"] = workflow_run_id
    # Pass through enrichment fields (parse JSON strings from Neo4j)
    for key in ("args_summary", "caller", "result_summary"):
        val = props.get(key)
        if val is None:
            continue
        if isinstance(val, str) and key != "caller":
            try:
                import json
                val = json.loads(val)
            except (ValueError, TypeError):
                pass
        evt[key] = val
    return evt


def _get_invoker():
    """Return the tool_invoker from the service registry, or None."""
    try:
        return get_service("tool_invoker")
    except Exception:
        return None


async def tool_invocation_stream(
    last_seen: int = 0,
) -> AsyncGenerator[dict[str, Any] | object, None]:
    """Yield tool invocation event dicts, or _SENTINEL_PING for keepalives.

    Callers should check ``event is _SENTINEL_PING`` to emit SSE keepalives.

    Always subscribes to the in-process event_bus so that events bridged
    from the events brick (swarm lifecycle, game events, etc.) are
    delivered in real time regardless of deployment topology.
    """
    queue: asyncio.Queue[dict[str, Any] | object] = asyncio.Queue(
        maxsize=200,
    )

    def _enqueue(item: dict[str, Any] | object) -> None:
        """Push item into queue, dropping oldest on overflow."""
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                queue.put_nowait(item)
            except Exception:
                pass

    async def _bus_reader() -> None:
        """Forward event_bus items into the shared queue.

        Filters out graph-poll noise (find_entities, graph_add_entity, etc.)
        from the instrumentation layer to prevent feedback loops.
        """
        async for item in event_bus.subscribe():
            if isinstance(item, dict):
                tool = item.get("tool", "")
                if tool and tool in _POLL_NOISE:
                    continue
            _enqueue(item)

    async def _brick_reader() -> None:
        """Forward graph-polled items into the shared queue."""
        async for item in _stream_via_brick(last_seen):
            _enqueue(item)

    tasks: list[asyncio.Task] = [asyncio.create_task(_bus_reader())]
    if _get_invoker() is not None:
        tasks.append(asyncio.create_task(_brick_reader()))

    last_keepalive = time.monotonic()
    try:
        while True:
            try:
                item = await asyncio.wait_for(
                    queue.get(), timeout=_KEEPALIVE_INTERVAL,
                )
            except asyncio.TimeoutError:
                yield _SENTINEL_PING
                last_keepalive = time.monotonic()
                continue
            yield item
            if time.monotonic() - last_keepalive >= _KEEPALIVE_INTERVAL:
                yield _SENTINEL_PING
                last_keepalive = time.monotonic()
    except asyncio.CancelledError:
        pass
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _stream_via_brick(
    last_seen: int,
) -> AsyncGenerator[dict[str, Any], None]:
    """Poll graph for ToolInvocation entities (cross-process)."""
    counter = 0
    seen_ids: set[str] = set()

    while True:
        try:
            invoker = _get_invoker()
            if invoker is None:
                await asyncio.sleep(_POLL_INTERVAL)
                continue

            result = invoker(
                "graph_find_entities",
                entity_type="ToolInvocation",
                limit=50,
            )
            entities = result.data.entities

            for entity in entities:
                entity_id = entity.id
                if entity_id in seen_ids:
                    continue
                seen_ids.add(entity_id)
                counter += 1
                if counter <= last_seen:
                    continue
                evt = _normalize_event(entity.properties)
                if evt is not None:
                    yield evt

            await asyncio.sleep(_POLL_INTERVAL)

        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.debug("tool_event_stream poll error: %s", exc)
            await asyncio.sleep(_POLL_INTERVAL)
