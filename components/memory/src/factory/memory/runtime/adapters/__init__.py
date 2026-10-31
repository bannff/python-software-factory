"""Memory backend adapters."""

from factory.memory.runtime.adapters.memory import InMemoryStore

__all__ = ["InMemoryStore"]

# Lazy imports for optional backends:
# from factory.memory.runtime.adapters.neo4j import Neo4jMemoryStore
# from factory.memory.runtime.adapters.amem import AMemStore
