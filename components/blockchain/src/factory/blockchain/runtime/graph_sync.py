"""Opportunistic graph sync for blockchain entities.

Keeps the default mock ledger visible in the graph when the graph brick is
available, so dashboard graph context works in local mode too.
"""

from __future__ import annotations

from typing import Any

from .models import Block, Bounty, Transaction, Wallet


def _get_invoker():
    try:
        from factory.mcp_utils.interface import get_service

        invoker = get_service("tool_invoker")
        if invoker is not None:
            return invoker
    except Exception:
        pass
    return None


def _invoke(tool_name: str, **kwargs: Any) -> Any:
    invoker = _get_invoker()
    if invoker is None:
        return None
    try:
        return invoker(tool_name, **kwargs)
    except Exception:
        return None


def sync_wallet(wallet: Wallet) -> None:
    _invoke(
        "graph_graph_add_entity",
        entity_id=wallet.wallet_id,
        entity_type="Wallet",
        properties=wallet.model_dump(),
    )


def sync_transaction(tx: Transaction) -> None:
    props = tx.model_dump()
    props["tx_type"] = str(tx.tx_type)
    props["status"] = str(tx.status)
    _invoke(
        "graph_graph_add_entity",
        entity_id=tx.tx_id,
        entity_type="Transaction",
        properties=props,
    )
    if tx.from_wallet:
        _invoke(
            "graph_graph_add_relationship",
            relationship_id=f"sent-{tx.tx_id}",
            relationship_type="SENT",
            source_id=tx.from_wallet,
            target_id=tx.tx_id,
        )
    if tx.to_wallet:
        _invoke(
            "graph_graph_add_relationship",
            relationship_id=f"recv-{tx.tx_id}",
            relationship_type="RECEIVED",
            source_id=tx.tx_id,
            target_id=tx.to_wallet,
        )


def sync_block(block: Block) -> None:
    _invoke(
        "graph_graph_add_entity",
        entity_id=f"block-{block.height}",
        entity_type="Block",
        properties=block.model_dump(),
    )
    if block.height > 0:
        _invoke(
            "graph_graph_add_relationship",
            relationship_id=f"prev-{block.height}",
            relationship_type="PREV_BLOCK",
            source_id=f"block-{block.height}",
            target_id=f"block-{block.height - 1}",
        )
    for tx_id in block.tx_ids:
        _invoke(
            "graph_graph_add_relationship",
            relationship_id=f"contains-{block.height}-{tx_id}",
            relationship_type="CONTAINS_TX",
            source_id=f"block-{block.height}",
            target_id=tx_id,
        )


def sync_bounty(bounty: Bounty) -> None:
    props = bounty.model_dump()
    props["status"] = str(bounty.status)
    _invoke(
        "graph_graph_add_entity",
        entity_id=bounty.bounty_id,
        entity_type="Bounty",
        properties=props,
    )
    _invoke(
        "graph_graph_add_relationship",
        relationship_id=f"posted-{bounty.bounty_id}",
        relationship_type="POSTED_BY",
        source_id=bounty.poster_wallet,
        target_id=bounty.bounty_id,
    )
    if bounty.escrow_tx_id:
        _invoke(
            "graph_graph_add_relationship",
            relationship_id=f"funded-{bounty.bounty_id}",
            relationship_type="FUNDED_BY",
            source_id=bounty.bounty_id,
            target_id=bounty.escrow_tx_id,
        )
    if bounty.claimer_wallet:
        _invoke(
            "graph_graph_add_relationship",
            relationship_id=f"claimed-{bounty.bounty_id}",
            relationship_type="CLAIMED_BOUNTY",
            source_id=bounty.claimer_wallet,
            target_id=bounty.bounty_id,
        )
    if bounty.release_tx_id:
        _invoke(
            "graph_graph_add_relationship",
            relationship_id=f"released-{bounty.bounty_id}",
            relationship_type="RELEASED_BY",
            source_id=bounty.bounty_id,
            target_id=bounty.release_tx_id,
        )