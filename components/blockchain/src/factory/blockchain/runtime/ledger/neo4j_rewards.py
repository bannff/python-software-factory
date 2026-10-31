"""Neo4j reward-escrow payout mixin (eval-gated release leg, epic #124 S4b).

Split from neo4j_bounty.py to honor the 200-LOC ratchet. Methods compose
with Neo4jLedger like the bounty mixin: Neo4jRewardMixin provides the
run-keyed ``BOUNTY_ESCROW`` park and idempotent ``BOUNTY_RELEASE`` credit.
"""
from __future__ import annotations

from typing import Any

from ..models import TransactionType
from .neo4j_ledger import _add_entity, _invoke


class Neo4jRewardMixin:
    """Reward-escrow methods for Neo4jLedger (graph-backed payout escrow)."""

    def escrow_reward(
        self, run_id: str, to_wallet: str, amount: float, memo: str = "",
    ) -> dict[str, Any]:
        existing = self.get_reward_escrow(run_id)  # type: ignore[attr-defined]
        # Released escrows are terminal: a redelivered reward.computed after
        # release must NOT re-escrow, or the next projection double-credits.
        if existing and existing.get("status") in ("escrowed", "released"):
            return existing
        rp = self._get_wallet_props(to_wallet)  # type: ignore[attr-defined]
        if not rp or amount <= 0:
            raise ValueError(f"Invalid reward escrow: wallet={to_wallet}, amount={amount}")
        escrow_tx = self._make_tx(  # type: ignore[attr-defined]
            TransactionType.BOUNTY_ESCROW, None, None, amount, memo,
        )
        self._commit_block([escrow_tx.tx_id])  # type: ignore[attr-defined]
        _add_entity(f"reward-escrow-{run_id}", "RewardEscrow", {
            "run_id": run_id, "wallet_id": to_wallet, "amount": amount,
            "escrow_tx_id": escrow_tx.tx_id, "memo": memo, "status": "escrowed",
        })
        _invoke("graph_graph_add_relationship",
                relationship_id=f"escrowed-{run_id}", relationship_type="REWARD_ESCROWED",
                source_id=to_wallet, target_id=f"reward-escrow-{run_id}",
                properties={"amount": amount})
        return {
            "run_id": run_id, "wallet_id": to_wallet, "amount": amount,
            "escrow_tx_id": escrow_tx.tx_id, "memo": memo, "status": "escrowed",
        }

    def release_reward(self, run_id: str) -> dict[str, Any]:
        record = self.get_reward_escrow(run_id)  # type: ignore[attr-defined]
        if record is None:
            raise ValueError(f"No pending reward escrow for run: {run_id}")
        if record.get("status") == "released":
            return {**record, "already_released": True}
        rp = self._get_wallet_props(record["wallet_id"])  # type: ignore[attr-defined]
        if not rp:
            raise ValueError(f"Wallet not found: {record['wallet_id']}")
        self._update_wallet_balance(  # type: ignore[attr-defined]
            record["wallet_id"], float(rp.get("balance", 0)) + record["amount"])
        release_tx = self._make_tx(  # type: ignore[attr-defined]
            TransactionType.BOUNTY_RELEASE, None, record["wallet_id"],
            record["amount"], record.get("memo") or f"reward release run {run_id}",
        )
        self._commit_block([release_tx.tx_id])  # type: ignore[attr-defined]
        _add_entity(f"reward-escrow-{run_id}", "RewardEscrow", {
            "run_id": run_id, "wallet_id": record["wallet_id"],
            "amount": record["amount"], "escrow_tx_id": record["escrow_tx_id"],
            "release_tx_id": release_tx.tx_id, "status": "released",
        })
        return {**record, "release_tx_id": release_tx.tx_id, "status": "released"}

    def get_reward_escrow(self, run_id: str) -> dict[str, Any] | None:
        try:
            r = _invoke("graph_graph_get_entity", entity_id=f"reward-escrow-{run_id}")
            if r and r.get("found"):
                return dict(r.get("properties", {}))
        except Exception:
            pass
        return None
