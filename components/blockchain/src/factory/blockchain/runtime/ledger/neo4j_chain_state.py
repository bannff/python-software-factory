"""Rehydrate and persist the Neo4j ledger's chain bookkeeping across restarts.

Wallets and transactions already live in the graph; the in-memory block list
and total supply did not, so a restart reset height to 0 (new blocks then
overwrote ``block-0``) and re-seeded supply from config. Blocks are re-read
from their ``Block`` entities and supply from a single ``ChainState`` entity.
``verify_blocks`` only checks stored hash fields, so ``tx_ids`` is not needed.
"""
from __future__ import annotations

from typing import Any, Callable

from ..models import Block

_STATE_ID = "chain-state"
_BLOCK_LIMIT = 100_000


def load_chain_state(invoke: Callable[..., Any], default_supply: float) -> tuple[list[Block], float]:
    """Return ``(blocks ordered by height, persisted total supply or default)``."""
    blocks: list[Block] = []
    try:
        found = invoke("graph_graph_find_entities", entity_type="Block", limit=_BLOCK_LIMIT)
        for entity in (found or {}).get("entities", []):
            props = entity.get("properties", {})
            blocks.append(Block(
                height=int(str(entity["id"]).removeprefix("block-")),
                hash=props["hash"], prev_hash=props["prev_hash"],
                merkle_root=props["merkle_root"], timestamp=props.get("created_at", ""),
            ))
        state = invoke("graph_graph_get_entity", entity_id=_STATE_ID)
    except Exception:  # noqa: BLE001 - graph unavailable: start fresh like before
        return [], default_supply
    blocks.sort(key=lambda b: b.height)
    supply = default_supply
    if state and state.get("found"):
        supply = float(state.get("properties", {}).get("total_supply", default_supply))
    return blocks, supply


def credit_supply(ledger: Any, add_entity: Callable[..., None], amount: float) -> None:
    """Grow supply by ``amount`` and persist it (mint / reward release only)."""
    ledger._total_supply += amount
    add_entity(_STATE_ID, "ChainState", {"total_supply": ledger._total_supply})


__all__ = ["credit_supply", "load_chain_state"]
