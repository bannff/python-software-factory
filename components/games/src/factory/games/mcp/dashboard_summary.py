"""Derived dashboard summary data for the games views."""

from __future__ import annotations

from collections import Counter
from typing import Any, TYPE_CHECKING

from ._summary_helpers import (
    _STATUS_ORDER,
    _activity_row,
    _game_entity_id,
    _game_row,
    _get_invoker,
    _graph_rows_from_entity,
    _status_rank,
)
from .learning_progress import build_learning_progress, learning_overview

if TYPE_CHECKING:
    from ..runtime.runtime import GamesRuntime


def build_dashboard_summary(runtime: "GamesRuntime") -> dict[str, Any]:
    """Aggregate games runtime data into dashboard-friendly structures."""
    games = runtime.list_games(limit=100)
    health = runtime.health_check()
    activities = list_recent_activity(limit=100)
    learning_runs = build_learning_progress(activities)
    graph_entities = list_related_graph_entities()
    game_rows = [_game_row(game.to_dict()) for game in games]

    activity_by_game: dict[str, list[dict[str, Any]]] = {}
    for activity in activities:
        game_id = str(activity.get("game_id", ""))
        if game_id:
            activity_by_game.setdefault(game_id, []).append(activity)

    for row in game_rows:
        game_activity = activity_by_game.get(str(row.get("game_id", "")), [])
        row["activity_count"] = len(game_activity)
        row["last_activity_type"] = game_activity[0].get("event_type") if game_activity else ""
        row["last_activity_label"] = game_activity[0].get("label") if game_activity else ""

    game_rows.sort(key=lambda item: (_status_rank(item["status"]), item.get("updated_at", "")))

    status_counts = Counter(str(item.get("status", "waiting")) for item in game_rows)
    series = [
        {"label": status.title(), "value": status_counts.get(status, 0)}
        for status in _STATUS_ORDER
        if status_counts.get(status, 0) or status == "active"
    ]

    return {
        "overview": {
            "games": len(game_rows),
            "active": status_counts.get("active", 0),
            "finished": status_counts.get("finished", 0),
            "draws": status_counts.get("draw", 0),
            "activity": len(activities),
            "graph_entities": len(graph_entities),
            "healthy": bool(health.get("healthy", False)),
            "backend": health.get("backend", "unknown"),
            **learning_overview(learning_runs),
        },
        "series": series,
        "learning_runs": learning_runs,
        "games": game_rows,
        "recent_activity": activities,
        "related_graph_entities": graph_entities,
    }


def list_recent_activity(limit: int = 20, game_id: str | None = None) -> list[dict[str, Any]]:
    """Return recent games activity from shared events history."""
    invoker = _get_invoker()
    if invoker is None:
        return []
    try:
        query_args: dict[str, Any] = {"source": "games", "limit": limit}
        if game_id:
            query_args["payload_key"] = "game_id"
            query_args["payload_value"] = game_id
        result = invoker("events_query_history", **query_args)
        entries = [entry.model_dump(mode="json") if hasattr(entry, "model_dump") else entry for entry in (result.data.entries if result and result.ok and result.data is not None else [])]
    except Exception:
        return []
    return [_activity_row(entry) for entry in entries if isinstance(entry, dict)][:limit]


def list_related_graph_entities(limit: int = 16, game_id: str | None = None) -> list[dict[str, Any]]:
    """Return game graph entities and nearby related entities."""
    invoker = _get_invoker()
    if invoker is None:
        return []
    try:
        if game_id:
            game_ids = [game_id]
        else:
            result = invoker("graph_find_entities", entity_type="GameSession", limit=limit)
            if not result or not result.ok or result.data is None:
                return []
            entities = result.data.entities
            game_ids = [
                str(entity.properties.get("game_id") or "")
                for entity in entities
            ]
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for current_game_id in game_ids:
            if not current_game_id:
                continue
            result = invoker("graph_get_entity", entity_id=_game_entity_id(current_game_id))
            entity = (
                result.data.entity.model_dump()
                if result and result.ok and result.data is not None and result.data.entity
                else {}
            )
            rows.extend(_graph_rows_from_entity(entity, focus_game_id=current_game_id, seen=seen))
            neighbors_result = invoker(
                "graph_get_neighbors",
                entity_id=_game_entity_id(current_game_id),
                direction="both",
            )
            neighbors = (
                neighbors_result.data.neighbors
                if neighbors_result and neighbors_result.ok and neighbors_result.data is not None
                else []
            )
            for neighbor in neighbors:
                rows.extend(_graph_rows_from_entity(neighbor.model_dump(), focus_game_id=current_game_id, seen=seen))
        return rows[:limit]
    except Exception:
        return []


__all__ = [
    "build_dashboard_summary",
    "list_recent_activity",
    "list_related_graph_entities",
]
