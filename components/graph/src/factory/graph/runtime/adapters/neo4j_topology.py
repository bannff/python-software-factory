"""Native bounded Cypher read for exact run topology."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ..ports import Entity, QueryResult, Relationship
from ..run_topology import assemble_topology, select_seed_entities, topology_caps

if TYPE_CHECKING:
    from .neo4j_adapter import Neo4jGraph

_RUN_EXPR = (
    "coalesce("
    "CASE WHEN r.run_id <> '' THEN r.run_id END, "
    "CASE WHEN r.workflow_run_id <> '' THEN r.workflow_run_id END, "
    "CASE WHEN r.browse_metadata.run_id <> '' THEN r.browse_metadata.run_id END, "
    "CASE WHEN r.browse_metadata.workflow_run_id <> '' "
    "THEN r.browse_metadata.workflow_run_id END, "
    "CASE WHEN r.browse_metadata.`managed_graph.run_id` <> '' "
    "THEN r.browse_metadata.`managed_graph.run_id` END)"
)
_EDGE_RETURN = (
    "coalesce(r.id, elementId(r)) AS id, type(r) AS type, "
    "a.id AS source_id, b.id AS target_id, properties(r) AS properties, "
    "head(labels(a)) AS source_type, labels(a) AS source_labels, "
    "properties(a) AS source_properties, head(labels(b)) AS target_type, "
    "labels(b) AS target_labels, properties(b) AS target_properties "
)


def get_run_topology(adapter: "Neo4jGraph", run_id: str, limit: int) -> QueryResult:
    caps = topology_caps(limit)
    seed_rows = _rows(adapter, (
        "MATCH (n) WHERE n.run_id = $run_id OR n.workflow_run_id = $run_id "
        "RETURN n.id AS id, head(labels(n)) AS type, labels(n) AS labels, "
        "properties(n) AS properties ORDER BY id LIMIT $seed_limit"
    ), {"run_id": run_id, "seed_limit": caps.seeds})
    seeds = select_seed_entities((_entity(row) for row in seed_rows), run_id, limit)
    seed_ids = [entity.id for entity in seeds]

    relationship_rows = _rows(adapter, (
        f"MATCH (a)-[r]->(b) WHERE {_RUN_EXPR} = $run_id RETURN {_EDGE_RETURN}"
        "ORDER BY id, source_id, target_id LIMIT $candidate_limit"
    ), {"run_id": run_id, "candidate_limit": caps.candidates})
    incident_rows = []
    if seed_ids:
        incident_rows = _rows(adapter, (
            "MATCH (a)-[r]->(b) WHERE (a.id IN $seed_ids OR b.id IN $seed_ids) "
            f"AND ({_RUN_EXPR} IS NULL OR {_RUN_EXPR} = $run_id) "
            f"RETURN {_EDGE_RETURN}ORDER BY id, source_id, target_id "
            "LIMIT $candidate_limit"
        ), {
            "run_id": run_id, "seed_ids": seed_ids,
            "candidate_limit": caps.candidates,
        })
    return assemble_topology(
        seeds, (_edge(row) for row in relationship_rows),
        (_edge(row) for row in incident_rows), run_id, limit,
    )


def _rows(adapter: "Neo4jGraph", query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    driver = adapter._get_driver()
    with driver.session(database=adapter._database) as session:
        return [dict(record) for record in session.run(query, **params)]


def _entity(row: dict[str, Any], prefix: str = "") -> Entity:
    properties = dict(row.get(f"{prefix}properties") or {})
    entity_id = str(row.get(f"{prefix}id") or properties.pop("id", ""))
    labels = list(row.get(f"{prefix}labels") or [])
    entity_type = str(row.get(f"{prefix}type") or (labels[0] if labels else "unknown"))
    return Entity(id=entity_id, type=entity_type, properties=properties, labels=labels[1:])


def _edge(row: dict[str, Any]) -> tuple[Relationship, Entity, Entity]:
    relationship = Relationship(
        id=str(row.get("id") or ""), type=str(row.get("type") or "unknown"),
        source_id=str(row.get("source_id") or ""),
        target_id=str(row.get("target_id") or ""),
        properties=dict(row.get("properties") or {}),
    )
    return relationship, _entity(row, "source_"), _entity(row, "target_")


__all__ = ["get_run_topology"]
