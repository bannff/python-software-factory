"""Graph-context reader for the sandbox dashboard.

Fetches the sandbox graph entity plus its nearby neighbors through the MCP tool
invoker (when graph storage is active) and shapes them into dashboard rows.
Best-effort: any invoker/transport failure degrades to an empty list.
"""

from __future__ import annotations

from typing import Any

from .dashboard_format import sandbox_entity_id
from .dashboard_invoker import entity_dict, envelope_data, get_invoker

_GRAPH_TITLE_MAP = {
    "SandboxEnvironment": "Sandbox Entity",
    "WorkflowRun": "Workflow Run",
    "WorkflowStep": "Workflow Step",
    "EvaluationRun": "Eval Run",
    "Event": "Event",
    "Metric": "Metric",
    "Finding": "Finding",
}


def list_related_graph_entities(limit: int = 16, env_id: str | None = None) -> list[dict[str, Any]]:
    """Return sandbox entities and nearby graph neighbors when graph storage is active."""
    invoker = get_invoker()
    if invoker is None:
        return []

    try:
        if env_id:
            env_ids = [env_id]
        else:
            env_result = invoker(
                "graph_graph_find_entities", entity_type="SandboxEnvironment", limit=limit,
            )
            entities = envelope_data(env_result).get("entities", [])
            env_ids = [str(entity_dict(e).get("properties", {}).get("env_id") or "") for e in entities]

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for candidate_env_id in env_ids:
            if not candidate_env_id:
                continue
            entity_result = invoker(
                "graph_graph_get_entity", entity_id=sandbox_entity_id(candidate_env_id),
            )
            entity = envelope_data(entity_result).get("entity")
            if entity is not None:
                rows.extend(graph_rows_from_entity(
                    entity_dict(entity), focus_env_id=candidate_env_id, seen=seen,
                ))

            neighbors_result = invoker(
                "graph_graph_get_neighbors",
                entity_id=sandbox_entity_id(candidate_env_id),
                direction="both",
            )
            neighbors = envelope_data(neighbors_result).get("neighbors", [])
            for neighbor in neighbors:
                rows.extend(graph_rows_from_entity(
                    entity_dict(neighbor), focus_env_id=candidate_env_id, seen=seen,
                ))
        return rows[:limit]
    except Exception:
        return []


def graph_rows_from_entity(
    entity: dict[str, Any],
    *,
    focus_env_id: str,
    seen: set[str],
) -> list[dict[str, Any]]:
    """Shape a graph entity into a dashboard row, deduping via ``seen``."""
    entity_id = str(entity.get("id") or entity.get("entity_id") or "")
    if not entity_id or entity_id in seen:
        return []

    seen.add(entity_id)
    props = entity.get("properties") if isinstance(entity.get("properties"), dict) else {}
    entity_type = str(entity.get("type") or entity.get("entity_type") or props.get("type") or "Entity")
    title = str(
        props.get("name")
        or props.get("title")
        or props.get("env_id")
        or props.get("run_id")
        or entity_id
    )
    subtitle = str(props.get("status") or props.get("phase") or entity_type)
    detail_parts = []
    for key in ("env_id", "run_id", "profile", "created_at"):
        value = props.get(key)
        if value not in (None, ""):
            detail_parts.append(f"{key}={value}")
    return [{
        "entity_id": entity_id,
        "entity_type": entity_type,
        "label": _GRAPH_TITLE_MAP.get(entity_type, entity_type),
        "title": title,
        "subtitle": subtitle,
        "detail": ", ".join(detail_parts),
        "focus_env_id": focus_env_id,
        "properties": props,
    }]
