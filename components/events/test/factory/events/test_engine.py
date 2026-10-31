from datetime import datetime, timedelta, timezone

import pytest

from factory.events.runtime.models import Event, EventFilter
from factory.events.runtime.adapters import SQLiteEventStore


@pytest.mark.asyncio
async def test_emit_and_query(runtime):
    # Emit an event
    event = Event(source="unit-test", type="test.event", payload={"foo": "bar"})
    event_id = await runtime.emit(event)
    assert event_id == event.id

    # Query it back
    results = await runtime.query(EventFilter(source="unit-test"))
    assert len(results.events) == 1
    assert results.events[0].id == event_id
    assert results.events[0].payload["foo"] == "bar"


@pytest.mark.asyncio
async def test_filtering(runtime):
    # Emit multiple events
    await runtime.emit(Event(source="src-a", type="type.a", payload={}))
    await runtime.emit(Event(source="src-b", type="type.b", payload={}))

    # Test Filter by Source
    results = await runtime.query(EventFilter(source="src-a"))
    assert len(results.events) == 1
    assert results.events[0].source == "src-a"

    # Test Filter by Type Prefix
    results = await runtime.query(EventFilter(type_prefix="type."))
    assert len(results.events) == 2


@pytest.mark.asyncio
async def test_prune(runtime):
    old_time = datetime.now(timezone.utc) - timedelta(days=2)
    recent_time = datetime.now(timezone.utc)

    # Manually insert old event to bypass auto-timestamp
    old_event = Event(source="old", type="test", timestamp=old_time)
    await runtime.emit(old_event)

    # Insert new event
    await runtime.emit(Event(source="new", type="test"))

    # Verify count
    assert await runtime.count() == 2

    # Prune
    deleted = await runtime.prune(recent_time - timedelta(days=1))

    assert (
        deleted >= 1
    )  # Note: SQLite timestamp compare string handling can be tricky, relying on isoformat
    assert await runtime.count() == 1
