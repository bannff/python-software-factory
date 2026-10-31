"""Bounded authority-scoped neighborhood traversal for NetworkX."""
from __future__ import annotations

import heapq
from collections.abc import Iterator
from typing import Any, TYPE_CHECKING

from ..neighborhood import (
    NeighborhoodRequest, NeighborhoodResult, matches_authority, validate_request,
)
from ..ports import Entity, Relationship

if TYPE_CHECKING:
    from .networkx_adapter import NetworkXGraph


def get_neighborhood(
    adapter: "NetworkXGraph", request: NeighborhoodRequest,
) -> NeighborhoodResult:
    validate_request(request)
    entities = {
        seed: entity for seed in request.seed_ids
        if (entity := adapter.get_entity(seed)) is not None
    }
    frontier = set(entities)
    relationships: dict[tuple[str, str, str], Relationship] = {}
    nodes_truncated = False
    edges_truncated = False
    depth_reached = 0
    for depth in range(1, request.max_depth + 1):
        remaining = request.edge_limit - len(relationships)
        if not frontier or remaining <= 0:
            edges_truncated = edges_truncated or bool(frontier)
            break
        candidates = heapq.nsmallest(
            remaining + 1,
            _candidates(adapter, frontier, request),
            key=lambda item: (item.id, item.source_id, item.target_id),
        )
        if len(candidates) > remaining:
            edges_truncated = True
            candidates = candidates[:remaining]
        next_frontier: set[str] = set()
        for relationship in candidates:
            neighbor = _neighbor(relationship, frontier, request.direction)
            if neighbor is None:
                continue
            if neighbor not in entities:
                if len(entities) >= request.node_limit:
                    nodes_truncated = True
                    continue
                entity = adapter.get_entity(neighbor)
                if entity is None:
                    continue
                entities[neighbor] = entity
                next_frontier.add(neighbor)
            if relationship.source_id in entities and relationship.target_id in entities:
                relationships[_key(relationship)] = relationship
        if candidates:
            depth_reached = depth
        frontier = next_frontier
    return NeighborhoodResult(
        entities=tuple(entities[key] for key in sorted(entities)),
        relationships=tuple(relationships[key] for key in sorted(relationships)),
        depth_reached=depth_reached,
        nodes_truncated=nodes_truncated,
        edges_truncated=edges_truncated,
    )


def _candidates(
    adapter: "NetworkXGraph", frontier: set[str], request: NeighborhoodRequest,
) -> Iterator[Relationship]:
    graph = adapter._get_graph()
    seen: set[tuple[str, str, str]] = set()
    for node_id in sorted(frontier):
        rows: list[tuple[Any, Any, Any, dict[str, Any]]] = []
        if request.direction in {"out", "both"}:
            rows.extend(graph.out_edges(node_id, data=True, keys=True))
        if request.direction in {"in", "both"}:
            rows.extend(graph.in_edges(node_id, data=True, keys=True))
        for source, target, key, data in rows:
            relationship = _relationship(source, target, key, data)
            identity = _key(relationship)
            if identity in seen or not _allowed(relationship, request):
                continue
            seen.add(identity)
            yield relationship


def _allowed(relationship: Relationship, request: NeighborhoodRequest) -> bool:
    return (
        (not request.relationship_types or relationship.type in request.relationship_types)
        and matches_authority(
            relationship.source_id, request.tenant_id, request.principal_id,
        )
        and matches_authority(
            relationship.target_id, request.tenant_id, request.principal_id,
        )
    )


def _relationship(source: Any, target: Any, key: Any, data: dict[str, Any]) -> Relationship:
    properties = {
        name: value for name, value in data.items() if name not in {"id", "type"}
    }
    return Relationship(
        id=str(data.get("id") or key), type=str(data.get("type") or "unknown"),
        source_id=str(source), target_id=str(target), properties=properties,
    )


def _neighbor(
    relationship: Relationship, frontier: set[str], direction: str,
) -> str | None:
    if direction in {"out", "both"} and relationship.source_id in frontier:
        return relationship.target_id
    if direction in {"in", "both"} and relationship.target_id in frontier:
        return relationship.source_id
    return None


def _key(relationship: Relationship) -> tuple[str, str, str]:
    return relationship.id, relationship.source_id, relationship.target_id


__all__ = ["get_neighborhood"]
