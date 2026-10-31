"""Back-compat shim — adapters now live under runtime/adapters/.

Deprecated. Import from factory.events.runtime.adapters instead. This
shim preserves the legacy public surface during the storage→adapters
rename so external callers keep working.
"""

from __future__ import annotations

# Protocol-based port (preferred for type hints)
from .ports import EventStore, EventHealth, EventStats

# Concrete implementations — re-exported from the new location
from .adapters import InMemoryEventStore, SQLiteEventStore

__all__ = [
    "EventStore",
    "EventHealth",
    "EventStats",
    "InMemoryEventStore",
    "SQLiteEventStore",
]
