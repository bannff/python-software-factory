"""Wallet listing for the Neo4j ledger (kept out of neo4j_ledger for its line budget)."""
from __future__ import annotations

from typing import Any, Callable

from ..models import Wallet


def list_wallets(invoke: Callable[..., Any], limit: int) -> list[Wallet]:
    result = invoke("graph_graph_find_entities", entity_type="Wallet", limit=limit)
    wallets = []
    for entity in (result or {}).get("entities", []):
        props = entity.get("properties", {})
        wallets.append(Wallet(
            wallet_id=entity["id"], owner_id=props.get("owner_id", ""),
            balance=float(props.get("balance", 0)), created_at=props.get("created_at", ""),
        ))
    return wallets
