"""Base class for event storage.

DEPRECATED: Use the Protocol-based EventStore from runtime/ports.py instead.
This module is kept for backward compatibility only.

New implementations should implement the EventStore Protocol directly
without inheriting from this class.
"""

import warnings
from datetime import datetime
from typing import List, Optional

from ..models import Event, EventFilter, EventQueryResult


class EventStore:
    """Abstract-ish base class for event storage.

    DEPRECATED: Implement the EventStore Protocol from runtime/ports.py instead.
    This class is kept for backward compatibility.
    """

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        warnings.warn(
            f"{cls.__name__} inherits from EventStore base class. "
            "Consider implementing the EventStore Protocol from runtime/ports.py instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    async def initialize(self):
        pass

    async def emit(self, event: Event) -> str:
        raise NotImplementedError

    async def query(self, filter: EventFilter) -> EventQueryResult:
        raise NotImplementedError

    async def prune(self, before: datetime) -> int:
        raise NotImplementedError

    async def count(self) -> int:
        raise NotImplementedError

    # Synchronous methods for non-async runtime compatibility
    def store(self, event: Event) -> str:
        """Synchronous store method. Should be overridden by subclasses."""
        raise NotImplementedError

    def get(self, event_id: str) -> Optional[Event]:
        """Synchronous get method. Should be overridden by subclasses."""
        raise NotImplementedError

    def list_events(
        self,
        event_type: str | None = None,
        source: str | None = None,
        limit: int = 100,
        offset: int = 0,
        descending: bool = True,
    ) -> List[Event]:
        """Synchronous list method. Should be overridden by subclasses."""
        raise NotImplementedError
