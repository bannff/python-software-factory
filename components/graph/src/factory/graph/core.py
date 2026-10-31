"""Core convenience functions for graph brick.

Provides simple top-level functions for common knowledge graph operations.
"""

from __future__ import annotations

from typing import Any

from .runtime.neighbor_limits import DEFAULT_NEIGHBOR_LIMIT
from .runtime.ports import Entity, Relationship, GraphPath
from .runtime.runtime import get_runtime

# Closed neutral verification-state set for Finding nodes
# (bd python-factory-216ti Contract B, meta-architect verdict ee6a3b0e).
# Domain-agnostic labels layered ABOVE security's SuspectedVuln/ProvenExploit.
FINDING_STATES: frozenset[str] = frozenset(
    {"candidate", "verifying", "verified", "refuted"}
)


def add_entity(
    entity_id: str,
    entity_type: str,
    properties: dict[str, Any] | None = None,
    labels: list[str] | None = None,
    backend: str = "networkx",
) -> Entity:
    """Add an entity to the knowledge graph."""
    runtime = get_runtime()
    graph = runtime.get_graph(backend)
    entity = Entity(id=entity_id, type=entity_type, properties=properties or {}, labels=labels or [])
    return graph.add_entity(entity)


def get_entity(entity_id: str, backend: str = "networkx") -> Entity | None:
    """Get an entity by ID."""
    runtime = get_runtime()
    graph = runtime.get_graph(backend)
    return graph.get_entity(entity_id)


def add_relationship(
    relationship_id: str,
    relationship_type: str,
    source_id: str,
    target_id: str,
    properties: dict[str, Any] | None = None,
    backend: str = "networkx",
) -> Relationship:
    """Add a relationship between entities."""
    runtime = get_runtime()
    graph = runtime.get_graph(backend)
    rel = Relationship(
        id=relationship_id,
        type=relationship_type,
        source_id=source_id,
        target_id=target_id,
        properties=properties or {},
    )
    return graph.add_relationship(rel)


def get_neighbors(
    entity_id: str,
    relationship_type: str | None = None,
    direction: str = "both",
    backend: str = "networkx",
    limit: int = DEFAULT_NEIGHBOR_LIMIT,
) -> list[Entity]:
    """Get neighboring entities."""
    runtime = get_runtime()
    graph = runtime.get_graph(backend)
    return graph.get_neighbors(
        entity_id, relationship_type, direction, limit=limit,
    )


def find_path(
    source_id: str,
    target_id: str,
    max_depth: int = 5,
    backend: str = "networkx",
) -> GraphPath | None:
    """Find shortest path between entities."""
    runtime = get_runtime()
    graph = runtime.get_graph(backend)
    return graph.find_path(source_id, target_id, max_depth)


def find_entities(
    entity_type: str | None = None,
    properties: dict[str, Any] | None = None,
    limit: int = 100,
    backend: str = "networkx",
) -> list[Entity]:
    """Find entities by type and/or properties."""
    runtime = get_runtime()
    graph = runtime.get_graph(backend)
    return graph.find_entities(entity_type, properties, limit)
