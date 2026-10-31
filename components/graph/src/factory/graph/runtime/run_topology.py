"""Shared bounded selection semantics for native run-topology adapters."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable

from .ports import Entity, QueryResult, Relationship

_RUN_KEYS = ("run_id", "workflow_run_id", "managed_graph.run_id")


@dataclass(frozen=True)
class TopologyCaps:
    """Independent output caps derived from the public request limit."""

    seeds: int
    relationships: int
    boundaries: int
    candidates: int


def topology_caps(limit: int) -> TopologyCaps:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
        raise ValueError("topology limit must be an integer between 1 and 200")
    return TopologyCaps(limit, limit, limit, limit * 2)


def run_values(properties: dict[str, Any]) -> set[str]:
    """Read non-empty canonical aliases from properties and browse metadata."""
    values = _values_from(properties)
    metadata = properties.get("browse_metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (TypeError, ValueError):
            metadata = None
    if isinstance(metadata, dict):
        values.update(_values_from(metadata))
    return values


def node_matches_run(entity: Entity, run_id: str) -> bool:
    values = _values_from(entity.properties)
    return values == {run_id}


def relationship_matches_run(relationship: Relationship, run_id: str) -> bool:
    return run_values(relationship.properties) == {run_id}


def relationship_is_foreign(relationship: Relationship, run_id: str) -> bool:
    values = run_values(relationship.properties)
    return bool(values and values != {run_id})


def select_seed_entities(entities: Iterable[Entity], run_id: str, limit: int) -> list[Entity]:
    cap = topology_caps(limit).seeds
    return sorted(
        (entity for entity in entities if node_matches_run(entity, run_id)),
        key=lambda entity: entity.id,
    )[:cap]


def assemble_topology(
    seeds: list[Entity], relationship_seeds: Iterable[tuple[Relationship, Entity, Entity]],
    incident: Iterable[tuple[Relationship, Entity, Entity]], run_id: str, limit: int,
) -> QueryResult:
    """Select persisted edges and one-hop endpoints without boundary traversal."""
    caps = topology_caps(limit)
    seed_by_id = {entity.id: entity for entity in seeds[:caps.seeds]}
    boundaries: dict[str, Entity] = {}
    relationships: list[Relationship] = []
    seen_edges: set[tuple[str, str, str, str]] = set()
    candidates = [(0, *item) for item in relationship_seeds]
    candidates.extend((1, *item) for item in incident)
    candidates.sort(key=lambda item: (item[0], *_relationship_key(item[1])))

    for _priority, relationship, source, target in candidates:
        key = _relationship_key(relationship)
        if key in seen_edges or len(relationships) >= caps.relationships:
            continue
        if relationship_is_foreign(relationship, run_id):
            continue
        endpoints = (source, target)
        if any(_invalid_boundary(entity, seed_by_id) for entity in endpoints):
            continue
        additions = {
            entity.id: entity for entity in endpoints
            if entity.id not in seed_by_id and entity.id not in boundaries
        }
        if len(boundaries) + len(additions) > caps.boundaries:
            continue
        boundaries.update(additions)
        relationships.append(relationship)
        seen_edges.add(key)

    relationships.sort(key=_relationship_key)
    entities = list(seed_by_id.values()) + [boundaries[key] for key in sorted(boundaries)]
    return QueryResult(entities=entities, relationships=relationships)


def _values_from(properties: dict[str, Any]) -> set[str]:
    values = {
        value.strip() for key in _RUN_KEYS
        if isinstance((value := properties.get(key)), str) and value.strip()
    }
    managed = properties.get("managed_graph")
    if isinstance(managed, dict):
        value = managed.get("run_id")
        if isinstance(value, str) and value.strip():
            values.add(value.strip())
    return values


def _invalid_boundary(entity: Entity, seeds: dict[str, Entity]) -> bool:
    if entity.id in seeds:
        return False
    values = _values_from(entity.properties)
    return bool(values)


def _relationship_key(relationship: Relationship) -> tuple[str, str, str, str]:
    return (
        relationship.id, relationship.source_id,
        relationship.target_id, relationship.type,
    )


__all__ = [
    "TopologyCaps", "assemble_topology", "node_matches_run", "relationship_matches_run",
    "run_values", "select_seed_entities", "topology_caps",
]
