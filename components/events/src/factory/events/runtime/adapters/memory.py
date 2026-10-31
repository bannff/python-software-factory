"""In-memory event store implementation.

Implements the EventStore Protocol from runtime/ports.py directly,
without inheriting from the deprecated base class.
"""

from datetime import datetime
from typing import List, Optional

from ..models import Event, EventFilter, EventQueryResult


class InMemoryEventStore:
    """Simple in-memory event store for testing and development.
    
    Implements the EventStore Protocol from runtime/ports.py.
    """

    def __init__(self):
        self._events: dict[str, Event] = {}

    async def initialize(self) -> None:
        """Initialize the store (no-op for in-memory)."""
        pass

    def store(self, event: Event) -> str:
        """Store an event in memory."""
        self._events[event.id] = event
        return event.id

    def get(self, event_id: str) -> Optional[Event]:
        """Get an event by ID."""
        return self._events.get(event_id)

    def list_events(
        self,
        event_type: str | None = None,
        source: str | None = None,
        limit: int = 100,
        offset: int = 0,
        descending: bool = True,
    ) -> List[Event]:
        """List events with pagination and optional filters."""
        events = list(self._events.values())

        if event_type:
            events = [e for e in events if e.type == event_type]
        if source:
            events = [e for e in events if e.source == source]

        events.sort(key=lambda e: e.timestamp, reverse=descending)
        return events[offset : offset + limit]

    async def emit(self, event: Event) -> str:
        """Async version of store."""
        return self.store(event)

    async def query(self, filter: EventFilter) -> EventQueryResult:
        """Query events with filtering."""
        events = list(self._events.values())

        if filter.source:
            events = [e for e in events if e.source == filter.source]
        if filter.type:
            events = [e for e in events if e.type == filter.type]
        elif filter.type_prefix:
            events = [e for e in events if e.type.startswith(filter.type_prefix)]
        if filter.trace_id:
            events = [e for e in events if e.trace_id == filter.trace_id]
        if filter.session_id:
            events = [e for e in events if e.session_id == filter.session_id]
        if filter.start_time:
            events = [e for e in events if e.timestamp >= filter.start_time]
        if filter.end_time:
            events = [e for e in events if e.timestamp <= filter.end_time]

        events.sort(key=lambda e: e.timestamp, reverse=filter.descending)
        total = len(events)
        events = events[filter.offset : filter.offset + filter.limit]

        return EventQueryResult(events=events, total_count=total)

    async def prune(self, before: datetime) -> int:
        """Remove events before a certain time."""
        to_delete = [
            event_id for event_id, event in self._events.items()
            if event.timestamp < before
        ]
        for event_id in to_delete:
            del self._events[event_id]
        return len(to_delete)

    async def count(self) -> int:
        """Count total events."""
        return len(self._events)
