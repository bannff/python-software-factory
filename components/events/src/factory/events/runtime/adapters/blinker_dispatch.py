"""Blinker-backed event dispatcher.

Wraps any EventStore and fires blinker signals when events are stored,
enabling in-process handler dispatch alongside persistent storage.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from blinker import Namespace

from factory.events.runtime.models import Event, EventFilter, EventQueryResult
from factory.events.runtime.ports import EventStore


class BlinkerEventStore:
    """EventStore decorator that fires blinker signals on store/emit.

    Usage:
        store = BlinkerEventStore(InMemoryEventStore())
        store.signals.signal("user.created").connect(my_handler)
        store.store(event)  # fires signal AND persists
    """

    def __init__(self, inner: EventStore) -> None:
        self._inner = inner
        self.signals = Namespace()

    async def initialize(self) -> None:
        await self._inner.initialize()

    def store(self, event: Event) -> str:
        result = self._inner.store(event)
        self.signals.signal(event.type).send(self, event=event)
        return result

    def get(self, event_id: str) -> Event | None:
        return self._inner.get(event_id)

    def list_events(
        self, event_type: str | None = None, source: str | None = None,
        limit: int = 100, offset: int = 0, descending: bool = True,
    ) -> list[Event]:
        return self._inner.list_events(event_type, source, limit, offset, descending)

    async def emit(self, event: Event) -> str:
        result = await self._inner.emit(event)
        self.signals.signal(event.type).send(self, event=event)
        return result

    async def query(self, filter: EventFilter) -> EventQueryResult:
        return await self._inner.query(filter)

    async def prune(self, before: datetime) -> int:
        return await self._inner.prune(before)

    async def count(self) -> int:
        return await self._inner.count()
