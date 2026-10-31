"""Bounded authority-scoped neighborhood traversal for Neo4j."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ..neighborhood import (
    NeighborhoodRequest, NeighborhoodResult, authority_tokens,
    matches_authority, validate_request,
)
from ..ports import Entity, Relationship

if TYPE_CHECKING:
    from .neo4j_adapter import Neo4jGraph

_RETURN = (
    "coalesce(r.id, elementId(r)) AS id, type(r) AS type, "
    "s.id AS source_id, t.id AS target_id, properties(r) AS properties, "
    "head(labels(s)) AS source_type, labels(s) AS source_labels, "
    "properties(s) AS source_properties, head(labels(t)) AS target_type, "
    "labels(t) AS target_labels, properties(t) AS target_properties "
)


def get_neighborhood(
    adapter: "Neo4jGraph", request: NeighborhoodRequest,
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
        rows = _rows(adapter, request, frontier, remaining + 1)
        if len(rows) > remaining:
            rows, edges_truncated = rows[:remaining], True
        next_frontier: set[str] = set()
        for row in rows:
            relationship, source, target = _candidate(row)
            if not _allowed(relationship, request):
                continue
            neighbor = _neighbor(relationship, frontier, request.direction)
            if neighbor is None:
                continue
            if neighbor not in entities:
                if len(entities) >= request.node_limit:
                    nodes_truncated = True
                    continue
                entity = target if target.id == neighbor else source
                entities[neighbor] = entity
                next_frontier.add(neighbor)
            if relationship.source_id in entities and relationship.target_id in entities:
                relationships[_key(relationship)] = relationship
        if rows:
            depth_reached = depth
        frontier = next_frontier
    return NeighborhoodResult(
        entities=tuple(entities[key] for key in sorted(entities)),
        relationships=tuple(relationships[key] for key in sorted(relationships)),
        depth_reached=depth_reached,
        nodes_truncated=nodes_truncated,
        edges_truncated=edges_truncated,
    )


def _rows(
    adapter: "Neo4jGraph", request: NeighborhoodRequest,
    frontier: set[str], limit: int,
) -> list[dict[str, Any]]:
    pattern = {
        "out": "MATCH (f)-[r]->(n) WHERE f.id IN $frontier ",
        "in": "MATCH (n)-[r]->(f) WHERE f.id IN $frontier ",
        "both": "MATCH (f)-[r]-(n) WHERE f.id IN $frontier ",
    }[request.direction]
    tenant, principal = authority_tokens(request.tenant_id, request.principal_id)
    query = (
        pattern
        + "WITH r, startNode(r) AS s, endNode(r) AS t "
        + "WHERE split(s.id, '~')[1] = $tenant "
        + "AND split(s.id, '~')[2] = $principal "
        + "AND split(t.id, '~')[1] = $tenant "
        + "AND split(t.id, '~')[2] = $principal "
        + "AND ($types = [] OR type(r) IN $types) "
        + f"RETURN {_RETURN}ORDER BY id, source_id, target_id LIMIT $limit"
    )
    driver = adapter._get_driver()
    with driver.session(database=adapter._database) as session:
        return [dict(row) for row in session.run(
            query, frontier=sorted(frontier), tenant=tenant,
            principal=principal, types=list(request.relationship_types), limit=limit,
        )]


def _candidate(row: dict[str, Any]) -> tuple[Relationship, Entity, Entity]:
    relationship = Relationship(
        id=str(row.get("id") or ""), type=str(row.get("type") or "unknown"),
        source_id=str(row.get("source_id") or ""),
        target_id=str(row.get("target_id") or ""),
        properties=dict(row.get("properties") or {}),
    )
    return relationship, _entity(row, "source_"), _entity(row, "target_")


def _entity(row: dict[str, Any], prefix: str) -> Entity:
    properties = dict(row.get(f"{prefix}properties") or {})
    entity_id = str(row.get(f"{prefix}id") or properties.pop("id", ""))
    labels = list(row.get(f"{prefix}labels") or [])
    entity_type = str(row.get(f"{prefix}type") or (labels[0] if labels else "unknown"))
    return Entity(entity_id, entity_type, properties, labels[1:])


def _allowed(relationship: Relationship, request: NeighborhoodRequest) -> bool:
    return all(matches_authority(
        value, request.tenant_id, request.principal_id,
    ) for value in (relationship.source_id, relationship.target_id))


def _neighbor(relationship: Relationship, frontier: set[str], direction: str) -> str | None:
    if direction in {"out", "both"} and relationship.source_id in frontier:
        return relationship.target_id
    if direction in {"in", "both"} and relationship.target_id in frontier:
        return relationship.source_id
    return None


def _key(relationship: Relationship) -> tuple[str, str, str]:
    return relationship.id, relationship.source_id, relationship.target_id


__all__ = ["get_neighborhood"]
