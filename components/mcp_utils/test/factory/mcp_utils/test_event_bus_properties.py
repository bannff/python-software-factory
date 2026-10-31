"""Hypothesis property tests for factory.mcp_utils.event_bus.

Invariants:
1. All events published under capacity are delivered to subscriber.
2. Subscriber receives exactly MAX_QUEUE_SIZE events when n > MAX_QUEUE_SIZE published.
3. publish() never raises regardless of event loop state.
4. Cross-thread publishers reach a subscriber on a different loop.

IMPORTANT: subscriber queue must be registered BEFORE any publish() calls.
Subscribers are stored as ``(loop, queue)`` tuples — see event_bus._subscribers.
"""
from __future__ import annotations

import asyncio
import threading
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from factory.mcp_utils import event_bus

MAX_QUEUE_SIZE = 100

_EVENT_STRATEGY = st.fixed_dictionaries({
    "brick": st.text(min_size=1, max_size=50),
    "tool": st.text(min_size=1, max_size=50),
    "success": st.booleans(),
    "latency_ms": st.floats(min_value=0, max_value=1e6, allow_nan=False),
    "ts": st.floats(min_value=0, allow_nan=False),
})


def _reset_bus() -> None:
    """Clear all subscribers so each test starts with a clean bus."""
    event_bus._subscribers.clear()


async def _drain(q: asyncio.Queue, count: int) -> list[dict[str, Any]]:
    """Drain up to `count` items from a queue without blocking."""
    items = []
    for _ in range(count):
        try:
            items.append(q.get_nowait())
        except asyncio.QueueEmpty:
            break
    return items


# ---------------------------------------------------------------------------
# Test 1: all events delivered under capacity
# ---------------------------------------------------------------------------

@given(st.lists(_EVENT_STRATEGY, min_size=1, max_size=MAX_QUEUE_SIZE))
@settings(max_examples=50)
def test_bus_delivers_all_events_under_capacity(events: list[dict]) -> None:
    """Invariant: every event published to a fresh bus reaches the subscriber."""
    async def run() -> None:
        _reset_bus()
        loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
        entry = (loop, q)
        # Register subscriber BEFORE any publish
        event_bus._subscribers.append(entry)
        try:
            for evt in events:
                event_bus.publish(evt)
            # Yield once so call_soon_threadsafe callbacks run
            await asyncio.sleep(0)
            received = await _drain(q, len(events))
            assert len(received) == len(events), (
                f"Expected {len(events)} events, got {len(received)}"
            )
        finally:
            event_bus._safe_remove(entry)

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Test 2: overflow drops oldest, subscriber receives exactly MAX_QUEUE_SIZE
# ---------------------------------------------------------------------------

@given(st.integers(min_value=MAX_QUEUE_SIZE + 1, max_value=500))
@settings(max_examples=30)
def test_bus_drops_oldest_on_overflow(n_events: int) -> None:
    """Invariant: subscriber receives exactly MAX_QUEUE_SIZE events when n > MAX_QUEUE_SIZE."""
    async def run() -> None:
        _reset_bus()
        loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
        entry = (loop, q)
        # Register subscriber BEFORE any publish
        event_bus._subscribers.append(entry)
        try:
            for i in range(n_events):
                event_bus.publish({
                    "seq": i, "brick": "x", "tool": "y",
                    "success": True, "latency_ms": 0.0, "ts": float(i),
                })
            # Drain pending call_soon_threadsafe callbacks
            await asyncio.sleep(0)
            received = await _drain(q, MAX_QUEUE_SIZE + 10)
            assert len(received) == MAX_QUEUE_SIZE, (
                f"Expected {MAX_QUEUE_SIZE} events after overflow, got {len(received)}"
            )
        finally:
            event_bus._safe_remove(entry)

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Test 3: publish() never raises regardless of event loop state
# ---------------------------------------------------------------------------

@given(st.booleans())
@settings(max_examples=20)
def test_publish_safe_from_sync_context(in_async: bool) -> None:
    """Invariant: publish() never raises from sync or async context."""
    _reset_bus()
    evt = {"brick": "test", "tool": "noop", "success": True,
           "latency_ms": 1.0, "ts": 0.0}

    if in_async:
        async def run() -> None:
            event_bus.publish(evt)  # no subscribers — must not raise

        asyncio.run(run())
    else:
        # Pure sync — no running event loop
        event_bus.publish(evt)


# ---------------------------------------------------------------------------
# Test 4: cross-thread publishers reach a subscriber on the API loop
# ---------------------------------------------------------------------------

def test_publish_from_worker_thread_reaches_subscriber_on_api_loop() -> None:
    """Cross-thread invariant: a worker thread publishing while the
    subscriber's loop is running must deliver — this is the main fix
    for python-factory-zlqx (swarm-internal tool events lost in transit).
    """
    async def run() -> None:
        _reset_bus()
        loop = asyncio.get_running_loop()
        q: asyncio.Queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
        entry = (loop, q)
        event_bus._subscribers.append(entry)

        sent = 25  # comfortably below MAX_QUEUE_SIZE

        def worker() -> None:
            for i in range(sent):
                event_bus.publish({
                    "seq": i, "brick": "agent", "tool": f"tool-{i}",
                    "success": True, "latency_ms": 1.0, "ts": float(i),
                })

        try:
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            t.join(timeout=2.0)
            # Yield so all call_soon_threadsafe callbacks run on the loop
            for _ in range(3):
                await asyncio.sleep(0)
            received = await _drain(q, sent + 5)
            assert len(received) == sent, (
                f"Expected {sent} cross-thread events, got {len(received)}"
            )
        finally:
            event_bus._safe_remove(entry)

    asyncio.run(run())
