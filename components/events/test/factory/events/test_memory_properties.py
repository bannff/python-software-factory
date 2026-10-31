"""Property-based tests for InMemoryEventStore using Hypothesis.

Tests that the store maintains correct state across arbitrary
sequences of operations and random inputs.
"""

import asyncio
from datetime import datetime, timedelta, timezone

from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from factory.events.runtime.models import Event, EventFilter
from factory.events.runtime.adapters.memory import InMemoryEventStore

SOURCES = ["agent", "workflow", "cache", "auth"]
TYPES = ["task.start", "task.end", "error", "info"]

event_st = st.builds(
    Event,
    source=st.sampled_from(SOURCES),
    type=st.sampled_from(TYPES),
    payload=st.fixed_dictionaries({}),
)


# --- @given property tests (sync operations) ---


@settings(max_examples=100)
@given(event=event_st)
def test_store_then_get_roundtrip(event: Event):
    """Storing an event then getting it returns the same event."""
    store = InMemoryEventStore()
    eid = store.store(event)
    retrieved = store.get(eid)
    assert retrieved is not None
    assert retrieved.id == event.id
    assert retrieved.source == event.source
    assert retrieved.type == event.type


@settings(max_examples=50)
@given(events=st.lists(event_st, min_size=0, max_size=20))
def test_store_n_returns_all(events: list[Event]):
    """Storing N events then listing returns all N."""
    store = InMemoryEventStore()
    for e in events:
        store.store(e)
    result = store.list_events(limit=1000)
    assert len(result) == len(events)


@settings(max_examples=50)
@given(
    events=st.lists(event_st, min_size=1, max_size=20),
    target_type=st.sampled_from(TYPES),
)
def test_list_filters_by_type(events: list[Event], target_type: str):
    """list_events(event_type=X) only returns events of type X."""
    store = InMemoryEventStore()
    for e in events:
        store.store(e)
    result = store.list_events(event_type=target_type)
    for e in result:
        assert e.type == target_type
    expected = sum(1 for e in events if e.type == target_type)
    assert len(result) == expected


@settings(max_examples=50)
@given(
    events=st.lists(event_st, min_size=1, max_size=20),
    target_source=st.sampled_from(SOURCES),
)
def test_list_filters_by_source(events: list[Event], target_source: str):
    """list_events(source=X) only returns events from source X."""
    store = InMemoryEventStore()
    for e in events:
        store.store(e)
    result = store.list_events(source=target_source)
    for e in result:
        assert e.source == target_source
    expected = sum(1 for e in events if e.source == target_source)
    assert len(result) == expected


@settings(max_examples=50)
@given(
    events=st.lists(event_st, min_size=1, max_size=30),
    limit=st.integers(min_value=1, max_value=10),
)
def test_list_respects_limit(events: list[Event], limit: int):
    """list_events(limit=N) returns at most N events."""
    store = InMemoryEventStore()
    for e in events:
        store.store(e)
    result = store.list_events(limit=limit)
    assert len(result) <= limit


# --- Async property tests ---


@settings(max_examples=50)
@given(events=st.lists(event_st, min_size=1, max_size=20))
def test_emit_then_count(events: list[Event]):
    """emit() increases count() by one for each event."""
    async def _run():
        store = InMemoryEventStore()
        for i, e in enumerate(events):
            await store.emit(e)
            assert await store.count() == i + 1
    asyncio.run(_run())


@settings(max_examples=50)
@given(events=st.lists(event_st, min_size=1, max_size=15))
def test_prune_removes_old_events(events: list[Event]):
    """prune(before=cutoff) removes events with timestamp < cutoff."""
    async def _run():
        store = InMemoryEventStore()
        for e in events:
            store.store(e)
        cutoff = datetime.now(timezone.utc) + timedelta(seconds=1)
        pruned = await store.prune(before=cutoff)
        assert pruned == len(events)
        assert await store.count() == 0
    asyncio.run(_run())


# --- RuleBasedStateMachine stateful test ---


class EventStoreStateMachine(RuleBasedStateMachine):
    """Stateful test: random store/get/list sequences must stay consistent."""

    def __init__(self):
        super().__init__()
        self.store = None
        self.model: dict[str, Event] = {}

    @initialize()
    def init_store(self):
        self.store = InMemoryEventStore()
        self.model = {}

    @rule(event=event_st)
    def store_event(self, event: Event):
        eid = self.store.store(event)
        self.model[eid] = event

    @rule(data=st.data())
    def get_existing(self, data):
        if not self.model:
            return
        eid = data.draw(st.sampled_from(sorted(self.model.keys())))
        result = self.store.get(eid)
        assert result is not None
        assert result.id == eid

    @rule(fake_id=st.uuids().map(str))
    def get_missing(self, fake_id: str):
        if fake_id not in self.model:
            assert self.store.get(fake_id) is None

    @rule()
    def list_all(self):
        result = self.store.list_events(limit=1000)
        assert len(result) == len(self.model)

    @invariant()
    def count_matches_model(self):
        if self.store is not None:
            assert asyncio.run(self.store.count()) == len(self.model)

    @invariant()
    def all_events_retrievable(self):
        if self.store is not None:
            for eid in self.model:
                assert self.store.get(eid) is not None


TestEventStoreStateful = EventStoreStateMachine.TestCase
