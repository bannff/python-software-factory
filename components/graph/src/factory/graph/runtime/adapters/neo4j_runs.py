"""Run-scoped typed Cypher queries for the Neo4j graph adapter.

Implements typed reads on ``KnowledgeGraph`` using native Cypher.
Tracked under bd j1lb / epic kzd8. ``taxonomy_edges`` (bd ecph9 / epic
hadbi): defaults live in :mod:`_taxonomy`; Finding-Cypher builder in
:mod:`_neo4j_finding`. The OPTIONAL MATCH + RETURN clauses are now
generated from ``TaxonomyEdgeSpec`` so this module carries no
domain-specific labels.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ..ports import Entity, QueryResult
from ._neo4j_finding import finding_query, safe_label
from ._taxonomy import TaxonomyEdgeSpec, resolve_edges

if TYPE_CHECKING:
    from .neo4j_adapter import Neo4jGraph

_INVOCATION_FIELDS = (
    "t.tool_name AS tool_name, t.brick_name AS brick, "
    "t.success AS success, t.latency_ms AS latency_ms, "
    "t.created_at AS created_at, t.error AS error, "
    "t.workflow_run_id AS workflow_run_id, "
    "t.args_summary AS args_summary, t.caller AS caller, "
    "t.result_summary AS result_summary, "
    "t.session_id AS invocation_session_id, "
    "t.principal_id AS principal_id, "
    "s.id AS session_id, s.agent_id AS session_agent_id, "
    "s.principal_id AS session_principal_id"
)


def _run_query(
    adapter: "Neo4jGraph", cypher: str, params: dict[str, Any],
) -> list[dict[str, Any]]:
    driver = adapter._get_driver()
    with driver.session(database=adapter._database) as session:
        result = session.run(cypher, **params)
        return [dict(record) for record in result]


def serialize_record(data: dict[str, Any]) -> dict[str, Any]:
    """Convert Neo4j Node/Relationship objects to plain dicts."""
    try:
        from neo4j.graph import Node, Relationship as NeoRel
    except ImportError:
        return data
    out: dict[str, Any] = {}
    for key, val in data.items():
        if isinstance(val, Node):
            out[key] = {"id": val.element_id, "labels": list(val.labels),
                        "properties": dict(val)}
        elif isinstance(val, NeoRel):
            out[key] = {"id": val.element_id, "type": val.type,
                        "start": val.start_node.element_id,
                        "end": val.end_node.element_id,
                        "properties": dict(val)}
        else:
            out[key] = val
    return out


def set_finding_state(
    adapter: "Neo4jGraph", finding_id: str, state: str,
) -> bool:
    """Atomically set ``Finding.state`` in a single Cypher statement.

    One ``MATCH ... SET ... RETURN`` (NOT read-modify-write) closes the
    r1pbn/xn0j9 race (bd python-factory-216ti Contract B). Returns True
    iff a Finding with ``finding_id`` existed and was written.
    """
    cypher = (
        "MATCH (f:Finding {id: $id}) SET f.state = $state "
        "RETURN f.id AS id"
    )
    rows = _run_query(adapter, cypher, {"id": finding_id, "state": state})
    return bool(rows)


def get_findings_for_run(
    adapter: "Neo4jGraph", run_id: str, app: str, limit: int,
    taxonomy_edges: list[TaxonomyEdgeSpec] | None = None,
) -> QueryResult:
    where = ["f.run_id = $run_id"]
    params: dict[str, Any] = {"run_id": run_id, "limit": int(limit)}
    if app:
        where.append("f.app = $app")
        params["app"] = app
    where_clause = f"WHERE {' AND '.join(where)} "
    cypher = finding_query(where_clause, resolve_edges(taxonomy_edges))
    return QueryResult(raw=_run_query(adapter, cypher, params))


def count_entities_by_run(
    adapter: "Neo4jGraph", run_id: str, labels: list[str],
) -> dict[str, int]:
    out: dict[str, int] = {}
    for label in labels:
        # Label cannot be a Cypher parameter — sanitize.
        sl = safe_label(label)
        if not sl:
            out[label] = 0
            continue
        cypher = (f"MATCH (n:{sl}) WHERE n.run_id = $run_id "
                  "RETURN count(n) AS c")
        rows = _run_query(adapter, cypher, {"run_id": run_id})
        out[label] = int(rows[0]["c"]) if rows else 0
    return out


def get_recent_findings(
    adapter: "Neo4jGraph", severity: str, app: str,
    run_id: str, limit: int,
    taxonomy_edges: list[TaxonomyEdgeSpec] | None = None,
) -> QueryResult:
    where: list[str] = []
    params: dict[str, Any] = {"limit": int(limit)}
    if severity:
        where.append("f.severity = $severity")
        params["severity"] = severity
    if app:
        where.append("f.app = $app")
        params["app"] = app
    if run_id:
        where.append("f.run_id = $run_id")
        params["run_id"] = run_id
    where_clause = f"WHERE {' AND '.join(where)} " if where else ""
    cypher = finding_query(where_clause, resolve_edges(taxonomy_edges))
    return QueryResult(raw=_run_query(adapter, cypher, params))


def get_target_app(
    adapter: "Neo4jGraph", target_app: str, run_id: str,
) -> Entity | None:
    params: dict[str, Any] = {"app": target_app}
    cypher = (
        "MATCH (n:TargetApp) WHERE n.app = $app OR n.name = $app "
        "RETURN n.id AS id ORDER BY "
    )
    if run_id:
        params["run_id"] = run_id
        cypher += "CASE WHEN n.last_recon_run_id = $run_id THEN 0 ELSE 1 END, "
    cypher += "n.created_at DESC LIMIT 1"
    rows = _run_query(adapter, cypher, params)
    if not rows:
        return None
    entity_id = rows[0].get("id")
    if not entity_id:
        return None
    return adapter.get_entity(str(entity_id))


def get_tool_invocations_for_run(
    adapter: "Neo4jGraph", run_id: str, limit: int,
) -> QueryResult:
    cypher = (
        "MATCH (t:ToolInvocation) WHERE t.workflow_run_id = $run_id "
        "RETURN t ORDER BY t.sequence ASC LIMIT $limit"
    )
    rows = _run_query(adapter, cypher, {"run_id": run_id, "limit": int(limit)})
    flattened: list[dict[str, Any]] = []
    for row in rows:
        node = row.get("t", {})
        # Coerce Node-or-dict shape into flat properties dict.
        if isinstance(node, dict) and "properties" in node:
            flattened.append({**node["properties"], "id": node.get("id", "")})
        elif isinstance(node, dict):
            flattened.append(node)
    return QueryResult(raw=flattened)


def list_recent_tool_invocations(
    adapter: "Neo4jGraph", limit: int, poll_noise: list[str],
) -> QueryResult:
    """Most-recent ToolInvocation rows, one-hop Session joined."""
    cypher = (
        "MATCH (t:ToolInvocation) "
        "OPTIONAL MATCH (s:Session)-[:CONTAINS_INVOCATION]->(t) "
        "WHERE NOT t.tool_name IN $poll_noise "
        f"RETURN {_INVOCATION_FIELDS} "
        "ORDER BY t.created_at DESC LIMIT $limit"
    )
    rows = _run_query(adapter, cypher, {
        "poll_noise": list(poll_noise), "limit": int(limit),
    })
    # Collapse t.session_id (denormalised) into s.id when null.
    for r in rows:
        if not r.get("session_id"):
            r["session_id"] = r.get("invocation_session_id")
        r.pop("invocation_session_id", None)
    return QueryResult(raw=rows)
