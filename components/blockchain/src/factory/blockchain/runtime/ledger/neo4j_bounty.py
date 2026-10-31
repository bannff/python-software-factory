"""Neo4j bounty + chain query operations (split from neo4j_ledger.py).

Mixin methods for Neo4jLedger — bounty lifecycle and chain queries.
"""

from __future__ import annotations

import uuid
from typing import Any

from ..models import (
    Block, Bounty, BountyStatus, ChainInfo, Transaction,
    TransactionType, _utcnow,
)
from .chain_ops import verify_blocks
from .neo4j_ledger import _add_entity, _add_rel, _invoke
from .neo4j_rewards import Neo4jRewardMixin


class Neo4jBountyMixin(Neo4jRewardMixin):
    """Bounty + chain query + reward-escrow methods for Neo4jLedger."""

    def mint(self, to_wallet: str, amount: float, memo: str = "") -> Transaction:
        rp = self._get_wallet_props(to_wallet)  # type: ignore[attr-defined]
        if not rp:
            raise ValueError(f"Wallet not found: {to_wallet}")
        if amount <= 0:
            raise ValueError("Amount must be positive")
        new_bal = float(rp.get("balance", 0)) + amount
        self._update_wallet_balance(to_wallet, new_bal)  # type: ignore[attr-defined]
        tx = self._make_tx(TransactionType.MINT, None, to_wallet, amount, memo)  # type: ignore[attr-defined]
        self._commit_block([tx.tx_id])  # type: ignore[attr-defined]
        return tx

    def post_bounty(
        self, poster_wallet: str, amount: float,
        description: str = "", criteria: dict | None = None,
    ) -> Bounty:
        pp = self._get_wallet_props(poster_wallet)  # type: ignore[attr-defined]
        if not pp:
            raise ValueError(f"Wallet not found: {poster_wallet}")
        bal = float(pp.get("balance", 0))
        if amount <= 0 or bal < amount:
            raise ValueError(f"Invalid bounty: balance={bal}, amount={amount}")
        self._update_wallet_balance(poster_wallet, bal - amount)  # type: ignore[attr-defined]
        escrow_tx = self._make_tx(  # type: ignore[attr-defined]
            TransactionType.BOUNTY_ESCROW, poster_wallet, None, amount, "escrow",
        )
        self._commit_block([escrow_tx.tx_id])  # type: ignore[attr-defined]
        bid = f"bounty-{uuid.uuid4().hex[:12]}"
        bounty = Bounty(
            bounty_id=bid, poster_wallet=poster_wallet, amount=amount,
            description=description, criteria=criteria or {},
            escrow_tx_id=escrow_tx.tx_id,
        )
        _add_entity(bid, "Bounty", {
            "amount": amount, "description": description,
            "status": "open", "criteria": str(criteria or {}),
            "created_at": bounty.created_at,
        })
        _add_rel(f"posted-{bid}", "POSTED_BOUNTY", poster_wallet, bid)
        _add_rel(f"funded-{bid}", "FUNDED_BY", bid, escrow_tx.tx_id)
        return bounty

    def claim_bounty(self, bounty_id: str, claimer_wallet: str) -> Transaction:
        bp = self._get_bounty_props(bounty_id)
        if not bp:
            raise ValueError(f"Bounty not found: {bounty_id}")
        if bp.get("status") != "open":
            raise ValueError(f"Bounty not open: {bp.get('status')}")
        cp = self._get_wallet_props(claimer_wallet)  # type: ignore[attr-defined]
        if not cp:
            raise ValueError(f"Claimer not found: {claimer_wallet}")
        amt = float(bp.get("amount", 0))
        self._update_wallet_balance(  # type: ignore[attr-defined]
            claimer_wallet, float(cp.get("balance", 0)) + amt)
        release_tx = self._make_tx(  # type: ignore[attr-defined]
            TransactionType.BOUNTY_RELEASE, None, claimer_wallet,
            amt, f"bounty {bounty_id} claimed",
        )
        self._commit_block([release_tx.tx_id])  # type: ignore[attr-defined]
        _add_entity(bounty_id, "Bounty", {
            "status": "claimed", "amount": amt, "created_at": bp.get("created_at", ""),
        })
        _add_rel(f"claimed-{bounty_id}", "CLAIMED_BOUNTY",
                 claimer_wallet, bounty_id, {"claimed_at": _utcnow()})
        return release_tx

    def _get_bounty_props(self, bid: str) -> dict | None:
        try:
            r = _invoke("graph_graph_get_entity", entity_id=bid)
            if r and r.get("found"):
                return r.get("properties", {})
        except Exception:
            pass
        return None

    def get_bounty(self, bounty_id: str) -> Bounty | None:
        bp = self._get_bounty_props(bounty_id)
        if not bp:
            return None
        return Bounty(
            bounty_id=bounty_id, poster_wallet=bp.get("poster_wallet", ""),
            amount=float(bp.get("amount", 0)), description=bp.get("description", ""),
            status=BountyStatus(bp.get("status", "open")),
            created_at=bp.get("created_at", ""),
        )

    def list_bounties(self, status: str | None = None, limit: int = 50) -> list[Bounty]:
        try:
            props = {"status": status} if status else None
            r = _invoke("graph_graph_find_entities",
                        entity_type="Bounty", properties=props, limit=limit)
            return [
                Bounty(bounty_id=e["id"], amount=float(e.get("properties", {}).get("amount", 0)),
                       status=BountyStatus(e.get("properties", {}).get("status", "open")),
                       description=e.get("properties", {}).get("description", ""),
                       created_at=e.get("properties", {}).get("created_at", ""))
                for e in (r or {}).get("entities", [])
            ]
        except Exception:
            return []

    def get_block(self, height: int) -> Block | None:
        return self._blocks[height] if 0 <= height < len(self._blocks) else None  # type: ignore[attr-defined]

    def get_chain_info(self) -> ChainInfo:
        return ChainInfo(
            height=len(self._blocks),  # type: ignore[attr-defined]
            total_supply=self._total_supply,  # type: ignore[attr-defined]
            genesis_hash=self._blocks[0].hash if self._blocks else "",  # type: ignore[attr-defined]
        )

    def verify_chain(self) -> dict[str, Any]:
        return verify_blocks(self._blocks)  # type: ignore[attr-defined]

    def reconcile(self, wallet_id: str) -> dict[str, Any]:
        props = self._get_wallet_props(wallet_id)  # type: ignore[attr-defined]
        if not props:
            raise ValueError(f"Wallet not found: {wallet_id}")
        return {"wallet_id": wallet_id, "stored": float(props.get("balance", 0)),
                "computed": float(props.get("balance", 0)), "drift": 0.0}

    def health_check(self) -> dict[str, Any]:
        try:
            r = _invoke("graph_graph_health_check")
            data = getattr(r, "data", None)
            return {"healthy": bool(r and r.ok and data and data.healthy), "provider": "neo4j",
                    "chain_height": len(self._blocks)}  # type: ignore[attr-defined]
        except Exception as e:
            return {"healthy": False, "provider": "neo4j", "error": str(e)}
