"""Neo4j-backed ledger via MCP aggregator pattern."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from ..models import (
    Block, Bounty, BountyStatus, ChainInfo, Transaction,
    TransactionStatus, TransactionType, Wallet, _utcnow,
)
from .chain_ops import _GENESIS_PREV, make_block, verify_blocks

logger = logging.getLogger(__name__)
_TREASURY_ID = "wallet-treasury"


def _get_aggregator() -> Any:
    from factory.mcp_server.interface import get_server, get_aggregator
    get_server()
    return get_aggregator()


def _invoke(tool_name: str, **kwargs: Any) -> Any:
    agg = _get_aggregator()
    if agg is None:
        raise RuntimeError("MCP aggregator not available")
    return agg.invoke_tool(tool_name, **kwargs)


def _add_entity(eid: str, etype: str, props: dict) -> None:
    _invoke("graph_graph_add_entity",
            entity_id=eid, entity_type=etype, properties=props)


def _add_rel(rid: str, rtype: str, src: str, tgt: str, props: dict | None = None) -> None:
    kw: dict[str, Any] = {
        "relationship_id": rid, "relationship_type": rtype,
        "source_id": src, "target_id": tgt,
    }
    if props:
        kw["properties"] = props
    _invoke("graph_graph_add_relationship", **kw)


class Neo4jLedger:
    """Graph-backed ledger implementing LedgerPort via MCP aggregator.

    Core wallet/transfer ops here. Bounty + chain queries in neo4j_bounty.py mixin.
    Compose with: class Neo4jLedgerFull(Neo4jBountyMixin, Neo4jLedger)
    """

    def __init__(self, total_supply: float = 1_000_000.0) -> None:
        self._total_supply = total_supply
        self._blocks: list[Block] = []
        self._init_genesis(total_supply)

    def _init_genesis(self, supply: float) -> None:
        # Skip if treasury already exists (server restart)
        if self._get_wallet_props(_TREASURY_ID):
            return
        _add_entity(_TREASURY_ID, "Wallet", {
            "owner_id": "treasury", "balance": supply, "created_at": _utcnow(),
        })
        tx = self._make_tx(TransactionType.MINT, None, _TREASURY_ID, supply, "genesis mint")
        self._commit_block([tx.tx_id])

    def _make_tx(
        self, tx_type: TransactionType, from_w: str | None,
        to_w: str | None, amount: float, memo: str,
    ) -> Transaction:
        tx_id = f"tx-{uuid.uuid4().hex[:12]}"
        tx = Transaction(
            tx_id=tx_id, tx_type=tx_type, from_wallet=from_w,
            to_wallet=to_w, amount=amount, memo=memo,
            status=TransactionStatus.COMMITTED,
        )
        _add_entity(tx_id, "Transaction", {
            "hash": tx_id, "tx_type": tx_type.value, "amount": amount,
            "memo": memo, "status": "committed", "created_at": tx.created_at,
        })
        if from_w:
            _add_rel(f"sent-{tx_id}", "SENT", from_w, tx_id)
        if to_w:
            _add_rel(f"recv-{tx_id}", "RECEIVED", tx_id, to_w)
        return tx

    def _commit_block(self, tx_ids: list[str]) -> Block:
        prev = self._blocks[-1].hash if self._blocks else _GENESIS_PREV
        block = make_block(len(self._blocks), prev, tx_ids)
        _add_entity(f"block-{block.height}", "Block", {
            "hash": block.hash, "prev_hash": block.prev_hash,
            "merkle_root": block.merkle_root, "tx_count": len(tx_ids),
            "created_at": block.timestamp,
        })
        if self._blocks:
            _add_rel(f"prev-{block.height}", "PREV_BLOCK",
                     f"block-{block.height}", f"block-{block.height - 1}")
        for tid in tx_ids:
            _add_rel(f"contains-{block.height}-{tid}", "CONTAINS_TX",
                     f"block-{block.height}", tid)
        self._blocks.append(block)
        return block

    def _update_wallet_balance(self, wid: str, new_balance: float) -> None:
        _add_entity(wid, "Wallet", {
            "balance": new_balance, "created_at": _utcnow(),
        })

    def _get_wallet_props(self, wid: str) -> dict | None:
        try:
            r = _invoke("graph_graph_get_entity", entity_id=wid)
            if r and r.get("found"):
                return r.get("properties", {})
        except Exception:
            pass
        return None

    # -- LedgerPort implementation --------------------------------------

    def create_wallet(self, owner_id: str, initial_balance: float = 0) -> Wallet:
        wid = f"wallet-{owner_id}"
        if self._get_wallet_props(wid):
            raise ValueError(f"Wallet already exists: {wid}")
        w = Wallet(wallet_id=wid, owner_id=owner_id, balance=0.0)
        _add_entity(wid, "Wallet", {
            "owner_id": owner_id, "balance": 0.0, "created_at": w.created_at,
        })
        if initial_balance > 0:
            self.transfer(_TREASURY_ID, wid, initial_balance, "initial allocation")
            w.balance = initial_balance
        return w

    def get_wallet(self, wallet_id: str) -> Wallet | None:
        props = self._get_wallet_props(wallet_id)
        if not props:
            return None
        return Wallet(
            wallet_id=wallet_id, owner_id=props.get("owner_id", ""),
            balance=float(props.get("balance", 0)), created_at=props.get("created_at", ""),
        )

    def transfer(
        self, from_wallet: str, to_wallet: str, amount: float, memo: str = "",
    ) -> Transaction:
        sp = self._get_wallet_props(from_wallet)
        rp = self._get_wallet_props(to_wallet)
        if not sp:
            raise ValueError(f"Sender not found: {from_wallet}")
        if not rp:
            raise ValueError(f"Receiver not found: {to_wallet}")
        sb = float(sp.get("balance", 0))
        if amount <= 0 or sb < amount:
            raise ValueError(f"Invalid transfer: balance={sb}, amount={amount}")
        self._update_wallet_balance(from_wallet, sb - amount)
        self._update_wallet_balance(to_wallet, float(rp.get("balance", 0)) + amount)
        tx = self._make_tx(TransactionType.TRANSFER, from_wallet, to_wallet, amount, memo)
        self._commit_block([tx.tx_id])
        return tx

    def get_balance(self, wallet_id: str) -> float:
        props = self._get_wallet_props(wallet_id)
        if not props:
            raise ValueError(f"Wallet not found: {wallet_id}")
        return float(props.get("balance", 0))

    def get_transactions(self, wallet_id: str | None = None, limit: int = 50) -> list[Transaction]:
        try:
            if wallet_id:
                r = _invoke("graph_graph_get_neighbors", entity_id=wallet_id,
                            relationship_type="SENT", direction="outgoing")
                ids = [n["id"] for n in (r or {}).get("neighbors", [])]
                r2 = _invoke("graph_graph_get_neighbors", entity_id=wallet_id,
                             relationship_type="RECEIVED", direction="incoming")
                ids += [n["id"] for n in (r2 or {}).get("neighbors", [])]
                return [self._tx_from_props(i) for i in ids[:limit] if i]
            r = _invoke("graph_graph_find_entities", entity_type="Transaction", limit=limit)
            return [self._tx_from_entity(e) for e in (r or {}).get("entities", [])]
        except Exception:
            return []

    def _tx_from_props(self, tx_id: str) -> Transaction:
        r = _invoke("graph_graph_get_entity", entity_id=tx_id)
        p = (r or {}).get("properties", {})
        return Transaction(
            tx_id=tx_id, tx_type=p.get("tx_type", "transfer"),
            amount=float(p.get("amount", 0)), memo=p.get("memo", ""),
            status=TransactionStatus.COMMITTED, created_at=p.get("created_at", ""),
        )

    def _tx_from_entity(self, e: dict) -> Transaction:
        p = e.get("properties", {})
        return Transaction(
            tx_id=e["id"], tx_type=p.get("tx_type", "transfer"),
            amount=float(p.get("amount", 0)), memo=p.get("memo", ""),
            status=TransactionStatus.COMMITTED, created_at=p.get("created_at", ""),
        )
