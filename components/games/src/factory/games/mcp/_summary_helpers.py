"""Row builders, graph helpers, and formatting for Games dashboard summaries."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


_STATUS_ORDER = ["active", "waiting", "finished", "draw"]
_ACTIVITY_TITLES = {
    "game.created": "Created",
    "game.move": "Move",
    "game.finished": "Finished",
}
_GRAPH_TITLE_MAP = {
    "GameSession": "Game Session",
    "GameMove": "Game Move",
    "WorkflowRun": "Workflow Run",
    "EvaluationRun": "Eval Run",
    "Metric": "Metric",
    "Finding": "Finding",
}


def _game_row(game: dict[str, Any]) -> dict[str, Any]:
    config = game.get("config") if isinstance(game.get("config"), dict) else {}
    updated_at = str(game.get("updated_at", ""))
    age_minutes = _age_minutes(updated_at or str(game.get("created_at", "")))
    winner = game.get("winner")
    players = game.get("players") if isinstance(game.get("players"), dict) else {}
    winner_name = players.get(winner) or players.get(str(winner)) if winner is not None else None
    return {
        **game,
        "run_id": config.get("run_id", ""),
        "graph_id": config.get("workflow_id") or config.get("graph_id", ""),
        "target_app": config.get("target_app", ""),
        "age_minutes": age_minutes,
        "age_label": _age_label(age_minutes),
        "winner_label": winner_name or (f"Player {winner}" if winner is not None else ""),
    }


def _activity_row(entry: dict[str, Any]) -> dict[str, Any]:
    payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
    event_type = str(entry.get("event_type", "game.activity"))
    age_minutes = _age_minutes(str(entry.get("timestamp", "")))
    return {
        "event_id": entry.get("event_id", ""),
        "event_type": event_type,
        "label": _ACTIVITY_TITLES.get(event_type, event_type.replace(".", " ").title()),
        "timestamp": entry.get("timestamp", ""),
        "age_label": _age_label(age_minutes),
        "game_id": payload.get("game_id", ""),
        "run_id": payload.get("run_id") or payload.get("workflow_run_id", ""),
        "graph_id": payload.get("graph_id", ""),
        "target_app": payload.get("target_app", ""),
        "workflow_type": payload.get("workflow_type", ""),
        "domain_class": payload.get("domain_class", ""),
        "vuln_class": payload.get("vuln_class", ""),
        "outcome": payload.get("outcome", ""),
        "detail": _activity_detail(event_type, payload),
        "payload": payload,
        "metadata": entry.get("metadata", {}),
    }


def _activity_detail(event_type: str, payload: dict[str, Any]) -> str:
    if event_type == "game.move":
        move = payload.get("move") if isinstance(payload.get("move"), dict) else {}
        if move.get("action"):
            return str(move.get("action"))
        if move.get("column") is not None:
            return f"column {move.get('column')}"
    if event_type == "game.finished":
        return f"winner {payload.get('winner')} after {payload.get('move_count', 0)} moves"
    if event_type == "game.created":
        return str(payload.get("game_type", "new game"))
    return ""


def _graph_rows_from_entity(entity: dict[str, Any], *, focus_game_id: str, seen: set[str]) -> list[dict[str, Any]]:
    entity_id = str(entity.get("id") or entity.get("entity_id") or "")
    if not entity_id or entity_id in seen:
        return []
    seen.add(entity_id)
    props = entity.get("properties") if isinstance(entity.get("properties"), dict) else {}
    entity_type = str(entity.get("type") or entity.get("entity_type") or "Entity")
    title = str(props.get("game_id") or props.get("run_id") or props.get("name") or entity_id)
    subtitle = str(props.get("status") or props.get("game_type") or entity_type)
    detail_parts = []
    for key in ("game_id", "run_id", "graph_id", "target_app"):
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
        "focus_game_id": focus_game_id,
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


def _game_entity_id(game_id: str) -> str:
    return f"game-{game_id}"


def _age_minutes(timestamp: str) -> int:
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - dt).total_seconds() // 60))
    except ValueError:
        return 0


def _age_label(age_minutes: int) -> str:
    if age_minutes < 1:
        return "just now"
    if age_minutes < 60:
        return f"{age_minutes}m"
    hours = age_minutes // 60
    if hours < 24:
        return f"{hours}h"
    return f"{hours // 24}d"


def _status_rank(status: str) -> int:
    order = {"active": 0, "waiting": 1, "finished": 2, "draw": 3}
    return order.get(status, 99)
