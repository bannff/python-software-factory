"""Run-scoped typed queries for the NetworkX graph adapter.

Implements typed reads on ``KnowledgeGraph`` for the in-memory backend,
plus ``cypher_loud_fail`` for ``query()``. Tracked under bd j1lb / c39g
/ epic kzd8. ``taxonomy_edges`` parameterisation: bd ecph9 (epic hadbi);
defaults live in :mod:`_taxonomy`.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from factory.mcp_utils.interface import POLL_NOISE

from ..ports import Entity, QueryResult
from ._taxonomy import TaxonomyEdgeSpec, resolve_edges
from ._run_columns import _FINDING_SCALAR_PROPS, _INVOCATION_SCALAR_PROPS

if TYPE_CHECKING:
    from .networkx_adapter import NetworkXGraph

_CYPHER_HINT = (
    "use graph_get_findings_for_run / graph_count_entities_by_run / "
    "graph_get_recent_findings / graph_get_target_app / "
    "graph_get_tool_invocations_for_run / "
    "graph_list_recent_tool_invocations / graph_find_entities."
)


def cypher_loud_fail(adapter: "NetworkXGraph", query_str: str) -> QueryResult:
    """Return a structured ``cypher_not_supported`` error for every shape."""
    return QueryResult(raw=[{
        "error": "cypher_not_supported",
        "backend": "networkx", "hint": _CYPHER_HINT,
    }])


def _row_for_finding(
    adapter: "NetworkXGraph", finding: Entity,
    edges: tuple[TaxonomyEdgeSpec, ...],
) -> dict[str, Any]:
    """Project Finding props + per-edge taxonomy neighbors into a flat row."""
    props = finding.properties
    row: dict[str, Any] = {k: props.get(k) for k in _FINDING_SCALAR_PROPS}
    row["id"] = row.get("id") or finding.id
    for edge in edges:
        # Pre-seed columns so missing edges still produce stable shape.
        for col in edge.target_props.values():
            row.setdefault(col, None)
        for n in adapter.get_neighbors(
            finding.id, edge.relationship_type, "out",
        ):
            if n.type != edge.target_label:
                continue
            for prop, col in edge.target_props.items():
                row[col] = n.properties.get(prop) or row.get(col)
            break  # one match per edge spec
    return row


def _matches(props: dict[str, Any], key: str, expected: str) -> bool:
    """Wildcard filter: empty ``expected`` = no filter."""
    return not expected or str(props.get(key, "")) == expected


def get_findings_for_run(
    adapter: "NetworkXGraph", run_id: str, app: str, limit: int,
    taxonomy_edges: list[TaxonomyEdgeSpec] | None = None,
) -> QueryResult:
    if not run_id:  # bd j6uo: identity-bearing, empty matches none.
        return QueryResult(raw=[])
    edges = resolve_edges(taxonomy_edges)
    findings = adapter.find_entities(entity_type="Finding", limit=10_000)
    rows = [
        _row_for_finding(adapter, e, edges) for e in findings
        if str(e.properties.get("run_id", "")) == run_id
        and _matches(e.properties, "app", app)
    ]
    rows.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
    return QueryResult(raw=rows[: max(0, int(limit))])


def count_entities_by_run(
    adapter: "NetworkXGraph", run_id: str, labels: list[str],
) -> dict[str, int]:
    if not run_id:  # bd j6uo: identity-bearing, empty zeros every label.
        return {label: 0 for label in labels}
    out: dict[str, int] = {}
    for label in labels:
        entities = adapter.find_entities(entity_type=label, limit=10_000)
        out[label] = sum(
            1 for e in entities
            if str(e.properties.get("run_id", "")) == run_id
        )
    return out


def get_recent_findings(
    adapter: "NetworkXGraph", severity: str, app: str,
    run_id: str, limit: int,
    taxonomy_edges: list[TaxonomyEdgeSpec] | None = None,
) -> QueryResult:
    edges = resolve_edges(taxonomy_edges)
    findings = adapter.find_entities(entity_type="Finding", limit=10_000)
    rows = [
        _row_for_finding(adapter, e, edges) for e in findings
        if _matches(e.properties, "severity", severity)
        and _matches(e.properties, "app", app)
        and _matches(e.properties, "run_id", run_id)
    ]
    rows.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
    return QueryResult(raw=rows[: max(0, int(limit))])


def get_target_app(
    adapter: "NetworkXGraph", target_app: str, run_id: str,
) -> Entity | None:
    candidates = [
        e for e in adapter.find_entities(entity_type="TargetApp", limit=10_000)
        if str(e.properties.get("app", "")) == target_app
        or str(e.properties.get("name", "")) == target_app
    ]
    if not candidates:
        return None
    if run_id:
        preferred = [
            e for e in candidates
            if str(e.properties.get("last_recon_run_id", "")) == run_id
        ]
        if preferred:
            candidates = preferred
    candidates.sort(
        key=lambda e: str(e.properties.get("created_at", "")), reverse=True,
    )
    return candidates[0]


def get_tool_invocations_for_run(
    adapter: "NetworkXGraph", run_id: str, limit: int,
) -> QueryResult:
    if not run_id:  # bd j6uo: identity-bearing, empty matches none.
        return QueryResult(raw=[])
    invocations = adapter.find_entities(
        entity_type="ToolInvocation",
        properties={"workflow_run_id": run_id}, limit=10_000,
    )
    rows = sorted(
        ({**inv.properties, "id": inv.id} for inv in invocations),
        key=lambda r: int(r.get("sequence", 0) or 0),
    )
    return QueryResult(raw=rows[: max(0, int(limit))])


def _row_for_invocation(
    adapter: "NetworkXGraph", invocation: Entity,
) -> dict[str, Any]:
    """Flat row + one-hop Session join (bd c39g, meta-architect Q3)."""
    props = invocation.properties
    row: dict[str, Any] = {k: props.get(k) for k in _INVOCATION_SCALAR_PROPS}
    row["brick"] = props.get("brick_name") or props.get("brick")
    row["id"] = invocation.id
    sid, sa, sp = props.get("session_id"), None, None
    for n in adapter.get_neighbors(invocation.id, "CONTAINS_INVOCATION", "in"):
        if n.type == "Session":
            sid = n.properties.get("id") or n.id or sid
            sa = n.properties.get("agent_id") or None
            sp = n.properties.get("principal_id") or None
            break
    row["session_id"], row["session_agent_id"], row["session_principal_id"] = sid, sa, sp
    return row


def list_recent_tool_invocations(
    adapter: "NetworkXGraph", limit: int,
) -> QueryResult:
    """Most-recent ToolInvocation rows globally, poll-noise filtered."""
    invocations = adapter.find_entities(
        entity_type="ToolInvocation", limit=10_000,
    )
    filtered = [
        inv for inv in invocations
        if str(inv.properties.get("tool_name", "")) not in POLL_NOISE
    ]
    filtered.sort(
        key=lambda e: str(e.properties.get("created_at", "")), reverse=True,
    )
    return QueryResult(raw=[
        _row_for_invocation(adapter, inv)
        for inv in filtered[: max(0, int(limit))]
    ])
