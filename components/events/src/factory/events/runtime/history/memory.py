"""In-memory implementation of the event history store."""

from __future__ import annotations

from collections import deque
from datetime import datetime

from .models import EventHistoryEntry


class InMemoryEventHistoryStore:
    """In-memory implementation of event history store.

    Implements the EventHistoryStore Protocol from runtime/ports.py.
    """

    def __init__(self, max_entries: int = 10000) -> None:
        self._max_entries = max_entries
        self._entries: deque[EventHistoryEntry] = deque(maxlen=max_entries)
        self._by_id: dict[str, EventHistoryEntry] = {}

    def record(self, entry: EventHistoryEntry) -> None:
        """Record an event in history."""
        # If at capacity, remove oldest from index
        if len(self._entries) >= self._max_entries:
            oldest = self._entries[0]
            self._by_id.pop(oldest.event_id, None)

        self._entries.append(entry)
        self._by_id[entry.event_id] = entry

    def get(self, event_id: str) -> EventHistoryEntry | None:
        """Get an event by ID."""
        return self._by_id.get(event_id)

    def list_entries(
        self,
        event_type: str | None = None,
        source: str | None = None,
        tenant_id: str | None = None,
        limit: int = 100,
    ) -> list[EventHistoryEntry]:
        """List event history entries with optional filters."""
        results = []
        # Iterate in reverse for most recent first
        for entry in reversed(self._entries):
            if event_type and entry.event_type != event_type:
                continue
            if source and entry.source != source:
                continue
            if tenant_id and entry.tenant_id != tenant_id:
                continue
            results.append(entry)
            if len(results) >= limit:
                break
        return results

    def clear(self) -> None:
        """Clear all entries."""
        self._entries.clear()
        self._by_id.clear()

    def prune(self, before: datetime) -> int:
        """Remove entries older than the cutoff timestamp."""
        remaining = [entry for entry in self._entries if entry.timestamp >= before]
        deleted = len(self._entries) - len(remaining)
        self._entries = deque(remaining, maxlen=self._max_entries)
        self._by_id = {entry.event_id: entry for entry in self._entries}
        return deleted

    def count(self) -> int:
        """Count total entries in history."""
        return len(self._entries)
