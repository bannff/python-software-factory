"""Aggregate-only blockchain dashboard summary assembly."""
from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

from .dashboard_rows import bounty_row, transaction_row

if TYPE_CHECKING:
    from ..runtime.runtime import BlockchainRuntime

_TX_TYPE_ORDER = ["transfer", "mint", "bounty_escrow", "bounty_release"]


def dashboard_summary(
    runtime: "BlockchainRuntime", transactions: list[dict[str, Any]], bounties: list[dict[str, Any]],
    activities: list[dict[str, Any]], graph_entities: list[dict[str, Any]],
) -> dict[str, Any]:
    ledger = runtime.get_ledger()
    info = ledger.get_chain_info().model_dump()
    by_tx, by_bounty = _activity_indexes(activities)
    tx_rows = [transaction_row(tx, by_tx.get(str(tx.get("tx_id", "")), [])) for tx in transactions]
    bounty_rows = [bounty_row(item, by_bounty.get(str(item.get("bounty_id", "")), [])) for item in bounties]
    counts = Counter(str(tx.get("tx_type", "transfer")) for tx in tx_rows)
    health = ledger.health_check()
    return {
        "overview": {"height": int(info.get("height", 0)), "wallets": int(info.get("wallet_count", 0)),
            "transactions": int(info.get("tx_count", 0)), "bounties": int(info.get("bounty_count", 0)),
            "activity": len(activities), "graph_entities": len(graph_entities),
            "provider": health.get("provider", "unknown"), "healthy": bool(health.get("healthy", False))},
        "series": [{"label": item.replace("_", " ").title(), "value": counts.get(item, 0)} for item in _TX_TYPE_ORDER if counts.get(item, 0) or item in {"transfer", "mint"}],
        "transactions": tx_rows, "bounties": bounty_rows, "recent_activity": activities,
        "related_graph_entities": graph_entities,
    }


def _activity_indexes(activities: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    by_tx: dict[str, list[dict[str, Any]]] = {}
    by_bounty: dict[str, list[dict[str, Any]]] = {}
    for activity in activities:
        for key, index in (("tx_id", by_tx), ("bounty_id", by_bounty)):
            value = str(activity.get(key, ""))
            if value:
                index.setdefault(value, []).append(activity)
    return by_tx, by_bounty
