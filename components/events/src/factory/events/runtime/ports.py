"""Abstract ports for events brick.

Ports define what capabilities the events system needs, not how they're implemented.
Adapters plug in specific backends (memory, SQLite, Redis, etc.)

Uses Protocol for structural subtyping - adapters don't need to inherit,
they just need to implement the required methods.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from .models import Event, EventFilter, EventQueryResult


@dataclass
class EventHealth:
    """Health status for an event store backend."""

    healthy: bool
    backend: str
    event_count: int = 0
    latency_ms: float = 0.0
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class EventStats:
    """Statistics for an event store."""

    total_events: int = 0
    events_by_type: dict[str, int] = field(default_factory=dict)
    oldest_event: datetime | None = None
    newest_event: datetime | None = None


@runtime_checkable
class EventStore(Protocol):
    """Port: Event storage with query and lifecycle support.

    Implementations must provide both sync and async methods.
    Sync methods (store, get, list_events) are for simple use cases.
    Async methods (emit, query, prune) are for high-throughput scenarios.
    """

    # Lifecycle
    async def initialize(self) -> None:
        """Initialize the store (create tables, connect, etc.)."""
        ...

    # Sync operations (for simple use cases)
    def store(self, event: Event) -> str:
        """Store an event. Returns the event ID."""
        ...

    def get(self, event_id: str) -> Event | None:
        """Get an event by ID. Returns None if not found."""
        ...

    def list_events(
        self,
        event_type: str | None = None,
        source: str | None = None,
        limit: int = 100,
        offset: int = 0,
        descending: bool = True,
    ) -> list[Event]:
        """List events with optional filters and pagination."""
        ...

    # Async operations (for high-throughput)
    async def emit(self, event: Event) -> str:
        """Async version of store. Returns the event ID."""
        ...

    async def query(self, filter: EventFilter) -> EventQueryResult:
        """Query events with advanced filtering."""
        ...

    async def prune(self, before: datetime) -> int:
        """Remove events older than timestamp. Returns count deleted."""
        ...

    async def count(self) -> int:
        """Count total events in the store."""
        ...


@runtime_checkable
class EventHistoryStore(Protocol):
    """Port: Event history storage for replay and audit.

    Separate from EventStore to allow different retention policies
    and storage backends for operational vs. historical data.
    """

    def record(self, entry: "EventHistoryEntry") -> None:
        """Record an event in history."""
        ...

    def get(self, event_id: str) -> "EventHistoryEntry | None":
        """Get a history entry by event ID."""
        ...

    def list_entries(
        self,
        event_type: str | None = None,
        source: str | None = None,
        tenant_id: str | None = None,
        limit: int = 100,
    ) -> list["EventHistoryEntry"]:
        """List history entries with optional filters."""
        ...

    def prune(self, before: datetime) -> int:
        """Remove history entries older than timestamp. Returns count deleted."""
        ...

    def count(self) -> int:
        """Count total history entries in the store."""
        ...


# Re-export EventHistoryEntry for convenience
from .history import EventHistoryEntry

__all__ = [
    "EventHealth",
    "EventStats",
    "EventStore",
    "EventHistoryStore",
    "EventHistoryEntry",
]
