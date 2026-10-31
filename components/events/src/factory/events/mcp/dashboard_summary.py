"""Derived dashboard summary data for Events views."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

from factory.mcp_utils.correlation import normalize_correlation

from ._summary_format import _age_label, _age_minutes
from ._summary_graph import _get_invoker, _graph_identifiers, _graph_rows_from_entity

if TYPE_CHECKING:
    from ..runtime.history import EventHistoryEntry
    from ..runtime.runtime import EventsRuntime


def build_dashboard_summary(runtime: "EventsRuntime") -> dict[str, Any]:
    entries = runtime.list_event_history(limit=200)
    subscriptions = runtime.get_subscription_registry().list_all()
    rows = [_event_row(entry) for entry in entries]
    graph_entities = list_related_graph_entities(rows=rows)
    type_counts = Counter(str(row.get("event_type", "event")) for row in rows)
    source_counts = Counter(str(row.get("source", "unknown")) for row in rows)

    series = [
        {"label": event_type, "value": count}
        for event_type, count in type_counts.most_common(8)
    ]
    source_series = [
        {"label": source, "value": count}
        for source, count in source_counts.most_common(8)
    ]

    return {
        "overview": {
            "events": len(rows),
            "sources": len(source_counts),
            "subscriptions": len(subscriptions),
            "graph_entities": len(graph_entities),
            "healthy": True,
            "retention_days": runtime.get_history_retention_days(),
        },
        "series": series,
        "source_series": source_series,
        "events": rows,
        "subscriptions": [_subscription_row(item) for item in subscriptions],
        "related_graph_entities": graph_entities,
    }


def get_history_entry(runtime: "EventsRuntime", event_id: str) -> dict[str, Any]:
    entry = runtime._history_store.get(event_id)  # noqa: SLF001
    if entry is None:
        return {"found": False, "event_id": event_id}
    return {"found": True, "entry": _serialize_entry(entry)}


def list_related_graph_entities(
    *,
    limit: int = 16,
    event_id: str | None = None,
    rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    invoker = _get_invoker()
    if invoker is None:
        return []

    candidate_rows = rows or []
    if event_id:
        candidate_rows = [row for row in candidate_rows if str(row.get("event_id", "")) == event_id]

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        for row in candidate_rows[:32]:
            focus_event_id = str(row.get("event_id", ""))
            identifiers = _graph_identifiers(row)
            for entity_id in identifiers.get("entity_ids", []):
                entity_result = invoker("graph_get_entity", entity_id=entity_id)
                entity = (
                    entity_result.data.entity
                    if entity_result.ok and entity_result.data is not None else None
                )
                if entity is not None:
                    results.extend(_graph_rows_from_entity(
                        entity.model_dump(), focus_event_id=focus_event_id, seen=seen,
                    ))
                neighbors_result = invoker(
                    "graph_get_neighbors",
                    entity_id=entity_id,
                    direction="both",
                )
                neighbors = (
                    neighbors_result.data.neighbors
                    if neighbors_result.ok and neighbors_result.data is not None else []
                )
                for neighbor in neighbors:
                    results.extend(_graph_rows_from_entity(
                        neighbor.model_dump(), focus_event_id=focus_event_id, seen=seen,
                    ))

            for key, value in identifiers.get("property_matches", []):
                search = invoker("graph_find_entities", properties={key: value}, limit=6)
                entities = (
                    search.data.entities if search.ok and search.data is not None else []
                )
                for entity in entities:
                    results.extend(_graph_rows_from_entity(
                        entity.model_dump(), focus_event_id=focus_event_id, seen=seen,
                    ))
    except Exception:
        return results[:limit]
    return results[:limit]


def _event_row(entry: "EventHistoryEntry") -> dict[str, Any]:
    payload = entry.payload if isinstance(entry.payload, dict) else {}
    metadata = entry.metadata if isinstance(entry.metadata, dict) else {}
    correlation = normalize_correlation(payload, metadata)
    age_minutes = _age_minutes(entry.timestamp.isoformat())
    return {
        "event_id": entry.event_id,
        "event_type": entry.event_type,
        "source": entry.source,
        "timestamp": entry.timestamp.isoformat(),
        "tenant_id": entry.tenant_id,
        "principal_id": entry.principal_id,
        "correlation_id": entry.correlation_id,
        "payload": payload,
        "metadata": metadata,
        "age_minutes": age_minutes,
        "age_label": _age_label(age_minutes),
        "label": entry.event_type,
        "detail": _event_detail(payload, metadata),
        "correlation": correlation,
        **correlation,
    }


def _serialize_entry(entry: "EventHistoryEntry") -> dict[str, Any]:
    return {
        "event_id": entry.event_id,
        "event_type": entry.event_type,
        "source": entry.source,
        "timestamp": entry.timestamp.isoformat(),
        "tenant_id": entry.tenant_id,
        "principal_id": entry.principal_id,
        "correlation_id": entry.correlation_id,
        "payload": entry.payload,
        "metadata": entry.metadata,
    }


def _subscription_row(subscription: Any) -> dict[str, Any]:
    return {
        "subscription_id": subscription.id,
        "event_type": subscription.event_type,
        "handler": subscription.handler,
        "enabled": bool(subscription.enabled),
        "priority": int(subscription.priority),
        "description": subscription.description or "",
        "has_filters": bool(subscription.filters),
    }


def _event_detail(payload: dict[str, Any], metadata: dict[str, Any]) -> str:
    for key in ("detail", "status", "step", "command", "target_app", "env_id", "run_id", "game_id"):
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    for key in ("entity_id", "graph_id", "correlation_id"):
        value = metadata.get(key)
        if value not in (None, ""):
            return f"{key}={value}"
    return ""
