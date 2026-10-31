"""Optional event-history projection for blockchain dashboard views."""
from __future__ import annotations

from typing import Any, Callable

from .dashboard_rows import age_label, age_minutes

_ACTIVITY_TITLES = {
    "blockchain.wallet.created": "Wallet Created",
    "blockchain.tx.committed": "Transaction Committed",
    "blockchain.bounty.posted": "Bounty Posted",
    "blockchain.bounty.claimed": "Bounty Claimed",
    "blockchain.bounty.cancelled": "Bounty Cancelled",
}


def recent_activity(
    invoker: Callable[..., Any] | None, limit: int, tx_id: str | None,
    bounty_id: str | None, wallet_id: str | None,
) -> list[dict[str, Any]]:
    if invoker is None:
        return []
    try:
        result = invoker("events_query_history", source="blockchain", limit=limit)
        entries = [
            entry.model_dump(mode="json") if hasattr(entry, "model_dump") else entry
            for entry in (result.data.entries if result and result.ok and result.data is not None else [])
        ]
    except Exception:
        return []
    rows = [_activity_row(entry) for entry in entries if isinstance(entry, dict)]
    if tx_id:
        rows = [row for row in rows if str(row.get("tx_id", "")) == tx_id]
    if bounty_id:
        rows = [row for row in rows if str(row.get("bounty_id", "")) == bounty_id]
    if wallet_id:
        rows = [row for row in rows if wallet_id in _wallet_ids(row)]
    return rows[:limit]


def _wallet_ids(row: dict[str, Any]) -> set[str]:
    return {str(row.get(key, "")) for key in (
        "wallet_id", "from_wallet", "to_wallet", "poster_wallet", "claimer_wallet",
    )}


def _activity_row(entry: dict[str, Any]) -> dict[str, Any]:
    payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
    event_type = str(entry.get("event_type", "blockchain.activity"))
    age = age_minutes(str(entry.get("timestamp", "")))
    return {
        "event_id": entry.get("event_id", ""), "event_type": event_type,
        "label": _ACTIVITY_TITLES.get(event_type, event_type.removeprefix("blockchain.").replace("_", " ").title()),
        "timestamp": entry.get("timestamp", ""), "age_label": age_label(age),
        "detail": _activity_detail(event_type, payload), "metadata": entry.get("metadata", {}), **payload,
    }


def _activity_detail(event_type: str, payload: dict[str, Any]) -> str:
    if event_type == "blockchain.tx.committed":
        return f"{payload.get('tx_type', '')} {payload.get('amount', '')}"
    if event_type == "blockchain.wallet.created":
        return str(payload.get("wallet_id", "wallet"))
    if event_type == "blockchain.bounty.posted":
        return f"posted {payload.get('amount', '')}"
    if event_type == "blockchain.bounty.claimed":
        return f"claimed by {payload.get('claimer_wallet', '')}"
    if event_type == "blockchain.bounty.cancelled":
        return "cancelled"
    return ""
