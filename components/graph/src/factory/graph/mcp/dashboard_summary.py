"""Derived dashboard summary data for Graph views."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..runtime.runtime import GraphRuntime


def build_dashboard_summary(runtime: "GraphRuntime") -> dict[str, Any]:
    graph = runtime.get_graph(runtime.default_backend)
    entities = graph.find_entities(limit=120)
    health = graph.health_check()

    rows = []
    neighborhood_rows: list[dict[str, Any]] = []
    seen_neighbors: set[str] = set()
    for entity in entities:
        neighbors = graph.get_neighbors(entity.id, direction="both")
        row = _entity_row(entity, neighbors)
        rows.append(row)
        neighborhood_rows.extend(
            _neighbor_rows(entity.id, neighbors, seen=seen_neighbors)
        )

    rows.sort(
        key=lambda item: (
            -int(item.get("neighbor_count", 0)),
            str(item.get("entity_type", "")),
            str(item.get("entity_id", "")),
        )
    )
    neighborhood_rows.sort(
        key=lambda item: (
            -int(item.get("shared_with_count", 0)),
            str(item.get("entity_type", "")),
            str(item.get("entity_id", "")),
        )
    )

    type_counts = Counter(str(row.get("entity_type", "Entity")) for row in rows)
    series = [
        {"label": entity_type, "value": count}
        for entity_type, count in type_counts.most_common(10)
    ]

    return {
        "overview": {
            "backend": runtime.default_backend,
            "nodes": int(health.node_count),
            "edges": int(health.edge_count),
            "healthy": bool(health.healthy),
            "entities": len(rows),
            "entity_types": len(type_counts),
            "neighborhoods": len(neighborhood_rows),
        },
        "series": series,
        "entities": rows,
        "neighborhoods": neighborhood_rows[:32],
    }


def get_entity_context(runtime: "GraphRuntime", entity_id: str, limit: int = 12) -> dict[str, Any]:
    graph = runtime.get_graph(runtime.default_backend)
    neighbors = graph.get_neighbors(entity_id, direction="both")
    rows = []
    seen: set[str] = set()
    for neighbor in neighbors:
        rows.extend(_neighbor_rows(entity_id, [neighbor], seen=seen))
    return {"entity_id": entity_id, "entries": rows[:limit], "count": len(rows[:limit])}


def _entity_row(entity: Any, neighbors: list[Any]) -> dict[str, Any]:
    props = entity.properties if isinstance(entity.properties, dict) else {}
    labels = list(entity.labels) if isinstance(entity.labels, list | tuple | set) else []
    age_label = _age_label(str(props.get("created_at", "")))
    return {
        "entity_id": entity.id,
        "entity_type": entity.type,
        "title": str(
            props.get("name")
            or props.get("title")
            or props.get("run_id")
            or props.get("env_id")
            or props.get("game_id")
            or entity.id
        ),
        "subtitle": str(props.get("status") or props.get("source") or entity.type),
        "labels": labels,
        "label_count": len(labels),
        "neighbor_count": len(neighbors),
        "property_count": len(props),
        "properties": props,
        "age_label": age_label,
        "detail": _detail(props),
    }


def _neighbor_rows(focus_entity_id: str, neighbors: list[Any], *, seen: set[str]) -> list[dict[str, Any]]:
    rows = []
    for neighbor in neighbors:
        entity_id = str(neighbor.id)
        if not entity_id or entity_id in seen:
            continue
        seen.add(entity_id)
        props = neighbor.properties if isinstance(neighbor.properties, dict) else {}
        rows.append(
            {
                "entity_id": entity_id,
                "entity_type": str(neighbor.type),
                "title": str(
                    props.get("name")
                    or props.get("title")
                    or props.get("run_id")
                    or props.get("env_id")
                    or props.get("game_id")
                    or entity_id
                ),
                "subtitle": str(props.get("status") or props.get("source") or neighbor.type),
                "focus_entity_id": focus_entity_id,
                "shared_with_count": 1,
                "detail": _detail(props),
                "properties": props,
            }
        )
    return rows


def _detail(properties: dict[str, Any]) -> str:
    parts = []
    for key in ("run_id", "env_id", "game_id", "target_app", "status", "source"):
        value = properties.get(key)
        if value not in (None, ""):
            parts.append(f"{key}={value}")
    return ", ".join(parts)


def _age_label(created_at: str) -> str:
    if not created_at:
        return ""
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_minutes = max(0, int((datetime.now(timezone.utc) - dt).total_seconds() // 60))
    except ValueError:
        return ""
    if age_minutes < 1:
        return "just now"
    if age_minutes < 60:
        return f"{age_minutes}m"
    hours = age_minutes // 60
    if hours < 24:
        return f"{hours}h"
    return f"{hours // 24}d"