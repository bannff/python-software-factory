"""Event storage implementations.

Available backends:
- InMemoryEventStore: Default, no persistence (dev/testing)
- SQLiteEventStore: File-based persistence
- RedisEventStore: Distributed pub/sub (requires redis package)
- Neo4jEventStore: Graph-based audit trail (requires neo4j package)

The EventStore Protocol is defined in runtime/ports.py.
The base.py module is kept for backward compatibility but deprecated.
"""

# Protocol-based port (preferred)
from ..ports import EventStore

# Concrete implementations
from .memory import InMemoryEventStore
from .sqlite import SQLiteEventStore
from .redis import RedisEventStore
from .neo4j import Neo4jEventStore

__all__ = ["EventStore", "InMemoryEventStore", "SQLiteEventStore", "RedisEventStore", "Neo4jEventStore"]
