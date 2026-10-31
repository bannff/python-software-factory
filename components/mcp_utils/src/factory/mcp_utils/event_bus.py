"""In-process event bus for tool call events.

Module-level singleton. Cross-thread-safe: subscribers register the loop
they live on; ``publish()`` schedules delivery via ``call_soon_threadsafe``
so worker threads (e.g. ``_AGENT_POOL``) can safely emit events to a
subscriber running on the API loop.

Pattern mirrors graph_sink.py: fire-and-forget, defence-in-depth.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

logger = logging.getLogger(__name__)

_MAX_QUEUE_SIZE = 100

# Module-level singleton: list of (loop, queue) tuples. The loop reference is
# what makes publish() cross-thread-safe — see ``publish``.
_subscribers: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = []


def _put_with_drop_oldest(q: asyncio.Queue, event: dict[str, Any]) -> None:
    """Enqueue an event onto the loop's queue, dropping the oldest on overflow.

    Runs on the queue's owning loop (called via ``call_soon_threadsafe``) so
    ``put_nowait``/``get_nowait`` are safe — ``asyncio.Queue`` is not itself
    thread-safe but is correct when accessed only from its loop.
    """
    try:
        q.put_nowait(event)
    except asyncio.QueueFull:
        try:
            q.get_nowait()
        except asyncio.QueueEmpty:
            pass
        try:
            q.put_nowait(event)
        except Exception:  # noqa: BLE001 — defence in depth
            pass


def publish(event: dict[str, Any]) -> None:
    """Publish an event to all subscribers across threads.

    Cross-thread-safe: every delivery goes through
    ``loop.call_soon_threadsafe(_put_with_drop_oldest, q, event)`` so a
    worker thread can publish to a subscriber whose queue is owned by a
    different event loop. Drops the oldest item on queue overflow. Swallows
    all errors — fire-and-forget.
    """
    try:
        dead: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = []
        for entry in list(_subscribers):
            loop, q = entry
            try:
                loop.call_soon_threadsafe(_put_with_drop_oldest, q, event)
            except RuntimeError:
                # Loop closed — prune the subscriber.
                dead.append(entry)
            except Exception:
                dead.append(entry)
        for entry in dead:
            _safe_remove(entry)
    except Exception:  # noqa: BLE001 — defence in depth
        logger.debug("event_bus.publish failed", exc_info=True)


async def subscribe() -> AsyncGenerator[dict[str, Any], None]:
    """Async generator that yields events for this subscriber.

    Records the running loop on entry so cross-thread publishers can
    schedule deliveries onto it via ``call_soon_threadsafe``. Removes the
    (loop, queue) entry on exit (disconnect / cancel).
    """
    loop = asyncio.get_running_loop()
    q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_MAX_QUEUE_SIZE)
    entry = (loop, q)
    _subscribers.append(entry)
    try:
        while True:
            event = await q.get()
            yield event
    finally:
        _safe_remove(entry)


def _safe_remove(
    entry: tuple[asyncio.AbstractEventLoop, asyncio.Queue],
) -> None:
    """Remove a (loop, queue) entry from subscribers without raising."""
    try:
        _subscribers.remove(entry)
    except ValueError:
        pass
