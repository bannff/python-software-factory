"""Tests for BlinkerEventStore adapter (blinker library).

Exercises real blinker signal dispatch — no mocks.
"""

from __future__ import annotations

import pytest

from factory.events.runtime.models import Event
from factory.events.runtime.adapters.blinker_dispatch import BlinkerEventStore
from factory.events.runtime.adapters.memory import InMemoryEventStore


@pytest.fixture
def store() -> BlinkerEventStore:
    inner = InMemoryEventStore()
    return BlinkerEventStore(inner)


class TestBlinkerEventStore:
    """Tests for BlinkerEventStore using real blinker library."""

    def test_import(self) -> None:
        """BlinkerEventStore and blinker are importable."""
        from blinker import Namespace
        assert Namespace is not None
        assert BlinkerEventStore is not None

    def test_instantiation(self) -> None:
        """Can wrap an InMemoryEventStore."""
        inner = InMemoryEventStore()
        wrapped = BlinkerEventStore(inner)
        assert wrapped.signals is not None

    def test_store_persists_event(self, store: BlinkerEventStore) -> None:
        """store() persists to the inner store."""
        event = Event(source="test", type="user.created", payload={"name": "alice"})
        event_id = store.store(event)
        assert event_id is not None
        retrieved = store.get(event.id)
        assert retrieved is not None
        assert retrieved.type == "user.created"

    def test_store_fires_signal(self, store: BlinkerEventStore) -> None:
        """store() fires a blinker signal with the event type."""
        received: list[Event] = []

        def handler(sender, event=None, **kw):
            received.append(event)

        # Use weak=False to prevent garbage collection of handler
        store.signals.signal("order.placed").connect(handler, weak=False)
        event = Event(source="shop", type="order.placed", payload={"total": 42})
        store.store(event)

        assert len(received) == 1
        assert received[0].type == "order.placed"
        assert received[0].payload["total"] == 42

    def test_signal_only_fires_for_matching_type(self, store: BlinkerEventStore) -> None:
        """Signals are type-specific — unrelated types don't fire."""
        received: list[int] = []

        def handler(sender, **kw):
            received.append(1)

        store.signals.signal("user.deleted").connect(handler, weak=False)

        store.store(Event(source="test", type="user.created"))
        assert len(received) == 0

        store.store(Event(source="test", type="user.deleted"))
        assert len(received) == 1

    def test_multiple_subscribers(self, store: BlinkerEventStore) -> None:
        """Multiple handlers on the same signal all fire."""
        counts = {"a": 0, "b": 0}

        def handler_a(sender, **kw):
            counts["a"] += 1

        def handler_b(sender, **kw):
            counts["b"] += 1

        store.signals.signal("tick").connect(handler_a, weak=False)
        store.signals.signal("tick").connect(handler_b, weak=False)

        store.store(Event(source="clock", type="tick"))
        assert counts["a"] == 1
        assert counts["b"] == 1

    def test_list_events_delegates(self, store: BlinkerEventStore) -> None:
        """list_events() delegates to inner store."""
        store.store(Event(source="a", type="t1"))
        store.store(Event(source="b", type="t2"))
        events = store.list_events()
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_emit_fires_signal(self, store: BlinkerEventStore) -> None:
        """Async emit() also fires blinker signal."""
        received: list[Event] = []

        def handler(sender, event=None, **kw):
            received.append(event)

        store.signals.signal("async.event").connect(handler, weak=False)

        event = Event(source="async", type="async.event")
        await store.emit(event)

        assert len(received) == 1
        assert received[0].type == "async.event"
