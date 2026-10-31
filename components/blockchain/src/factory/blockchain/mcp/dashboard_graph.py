"""Optional graph-context projection for blockchain dashboard views."""
from __future__ import annotations

from typing import Any, Callable

_GRAPH_TITLE_MAP = {
    "Wallet": "Wallet", "Transaction": "Transaction", "Bounty": "Bounty", "Block": "Block",
    "WorkflowRun": "Workflow Run", "Metric": "Metric", "Finding": "Finding",
}


def related_graph_entities(
    invoker: Callable[..., Any] | None, limit: int, entity_id: str | None,
    transactions: list[dict[str, Any]] | None, bounties: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if invoker is None:
        return []
    ids = [entity_id] if entity_id else _entity_ids(transactions, bounties)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        for current_id in ids:
            if not current_id:
                continue
            entity = invoker("graph_graph_get_entity", entity_id=current_id) or {}
            rows.extend(_rows_from_entity(entity, current_id, seen))
            result = invoker("graph_graph_get_neighbors", entity_id=current_id, direction="both") or {}
            neighbors = result.get("neighbors", []) if isinstance(result, dict) else []
            for neighbor in neighbors:
                if isinstance(neighbor, dict):
                    rows.extend(_rows_from_entity(neighbor, current_id, seen))
    except Exception:
        return rows[:limit]
    return rows[:limit]


def _entity_ids(transactions: list[dict[str, Any]] | None, bounties: list[dict[str, Any]] | None) -> list[str]:
    rows = transactions or []
    ids = [str(item.get("tx_id", "")) for item in rows if item.get("tx_id")]
    return ids + [str(item.get("bounty_id", "")) for item in bounties or [] if item.get("bounty_id")]


def _rows_from_entity(entity: dict[str, Any], focus_id: str, seen: set[str]) -> list[dict[str, Any]]:
    entity_id = str(entity.get("id") or entity.get("entity_id") or "")
    if not entity_id or entity_id in seen:
        return []
    seen.add(entity_id)
    props = entity.get("properties") if isinstance(entity.get("properties"), dict) else {}
    entity_type = str(entity.get("type") or entity.get("entity_type") or props.get("type") or "Entity")
    title = str(props.get("wallet_id") or props.get("tx_id") or props.get("bounty_id") or props.get("name") or entity_id)
    detail = ", ".join(f"{key}={props[key]}" for key in ("wallet_id", "tx_id", "bounty_id", "poster_wallet", "claimer_wallet") if props.get(key) not in (None, ""))
    return [{
        "entity_id": entity_id, "entity_type": entity_type, "label": _GRAPH_TITLE_MAP.get(entity_type, entity_type),
        "title": title, "subtitle": str(props.get("status") or props.get("tx_type") or entity_type),
        "detail": detail, "focus_entity_id": focus_id, "properties": props,
    }]
