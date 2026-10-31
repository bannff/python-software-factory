"""Public dashboard-summary facade retaining optional integration behavior."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .dashboard_activity import recent_activity
from .dashboard_graph import related_graph_entities
from .dashboard_overview import dashboard_summary

if TYPE_CHECKING:
    from ..runtime.runtime import BlockchainRuntime


def build_dashboard_summary(runtime: "BlockchainRuntime") -> dict[str, Any]:
    """Build dashboard data, treating optional events and graph services as absent on failure."""
    ledger = runtime.get_ledger()
    transactions = [tx.model_dump() for tx in ledger.get_transactions(limit=100)]
    bounties = [bounty.model_dump() for bounty in ledger.list_bounties(limit=100)]
    activities = list_recent_activity()
    entities = list_related_graph_entities(transactions=transactions, bounties=bounties)
    return dashboard_summary(runtime, transactions, bounties, activities, entities)


def list_recent_activity(
    limit: int = 20,
    tx_id: str | None = None,
    bounty_id: str | None = None,
    wallet_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return optional event history, preserving an empty result on unavailable services."""
    return recent_activity(_get_invoker(), limit, tx_id, bounty_id, wallet_id)


def list_related_graph_entities(
    *,
    limit: int = 16,
    entity_id: str | None = None,
    transactions: list[dict[str, Any]] | None = None,
    bounties: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return optional graph context, preserving partial rows when a lookup fails."""
    return related_graph_entities(_get_invoker(), limit, entity_id, transactions, bounties)


def _get_invoker():
    try:
        from factory.mcp_utils.interface import get_service

        return get_service("tool_invoker")
    except Exception:
        return None
