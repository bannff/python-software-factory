"""Graph-entity helpers for Events dashboard summaries."""

from __future__ import annotations

from typing import Any

from factory.mcp_utils.correlation import normalize_correlation


_GRAPH_TITLE_MAP = {
    "WorkflowRun": "Workflow Run",
    "WorkflowDefinition": "Workflow Definition",
    "SandboxEnvironment": "Sandbox",
    "GameSession": "Game Session",
    "Transaction": "Transaction",
    "Wallet": "Wallet",
    "Bounty": "Bounty",
    "WorkflowEvent": "Workflow Activity",
    "Metric": "Metric",
    "Finding": "Finding",
}


def _graph_identifiers(row: dict[str, Any]) -> dict[str, list[Any]]:
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    correlation = normalize_correlation(payload, metadata)

    entity_ids: list[str] = []
    for key in ("entity_id", "graph_id"):
        value = correlation.get(key)
        if value:
            entity_ids.append(value)

    property_matches: list[tuple[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for source in (payload, metadata, correlation):
        for key, value in source.items():
            if not key.endswith("_id") and key not in {"target_app", "correlation_id"}:
                continue
            text = str(value).strip()
            if not text:
                continue
            pair = (str(key), text)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            property_matches.append(pair)
    return {"entity_ids": entity_ids, "property_matches": property_matches}


def _graph_rows_from_entity(entity: dict[str, Any], *, focus_event_id: str, seen: set[str]) -> list[dict[str, Any]]:
    entity_id = str(entity.get("id") or entity.get("entity_id") or "")
    if not entity_id or entity_id in seen:
        return []
    seen.add(entity_id)
    props = entity.get("properties") if isinstance(entity.get("properties"), dict) else {}
    entity_type = str(entity.get("type") or entity.get("entity_type") or props.get("type") or "Entity")
    title = str(
        props.get("name")
        or props.get("title")
        or props.get("event_type")
        or props.get("run_id")
        or props.get("env_id")
        or props.get("game_id")
        or entity_id
    )
    subtitle = str(props.get("status") or props.get("source") or entity_type)
    detail_parts = []
    for key in ("event_id", "run_id", "env_id", "game_id", "target_app"):
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
        "focus_event_id": focus_event_id,
        "properties": props,
    }]


def _get_invoker():
    try:
        from factory.mcp_utils.interface import get_service

        invoker = get_service("tool_invoker")
        if invoker is not None:
            return invoker
    except Exception:
        pass
    return None
