"""Native bounded run-topology read for NetworkX adapters."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ..ports import Entity, QueryResult, Relationship
from ..run_topology import (
    assemble_topology, relationship_matches_run, select_seed_entities,
)
from .networkx_edges import iter_edges

if TYPE_CHECKING:
    from .networkx_adapter import NetworkXGraph


def get_run_topology(adapter: "NetworkXGraph", run_id: str, limit: int) -> QueryResult:
    graph = adapter._get_graph()
    entities = [adapter.get_entity(str(node_id)) for node_id in graph.nodes]
    seeds = select_seed_entities(
        (entity for entity in entities if entity is not None), run_id, limit,
    )
    seed_ids = {entity.id for entity in seeds}
    relationship_seeds: list[tuple[Relationship, Entity, Entity]] = []
    incident: list[tuple[Relationship, Entity, Entity]] = []

    for source_id, target_id, key, data in iter_edges(graph):
        candidate = _candidate(adapter, source_id, target_id, key, data)
        if candidate is None:
            continue
        relationship, _source, _target = candidate
        if relationship_matches_run(relationship, run_id):
            relationship_seeds.append(candidate)
        if relationship.source_id in seed_ids or relationship.target_id in seed_ids:
            incident.append(candidate)
    return assemble_topology(seeds, relationship_seeds, incident, run_id, limit)


def _candidate(
    adapter: "NetworkXGraph", source_id: Any, target_id: Any,
    key: Any, data: dict[str, Any],
) -> tuple[Relationship, Entity, Entity] | None:
    source = adapter.get_entity(str(source_id))
    target = adapter.get_entity(str(target_id))
    if source is None or target is None:
        return None
    properties = {name: value for name, value in data.items() if name not in {"id", "type"}}
    relationship = Relationship(
        id=str(data.get("id") or key), type=str(data.get("type") or "unknown"),
        source_id=source.id, target_id=target.id, properties=properties,
    )
    return relationship, source, target


__all__ = ["get_run_topology"]
