"""Reward-escrow payout primitives for the MockLedger facade.

The eval-gated payout path (epic #124 S4b) parks a reward as a
``BOUNTY_ESCROW`` transaction at compute time and credits the wallet only on
``release_reward`` — the leg fired by the eval projection once durable eval
evidence exists for the run. Idempotency: escrow keyed ``escrowed:{run_id}``,
release keyed ``released:{run_id}`` (a duplicate release produces exactly one
wallet movement).
"""
from __future__ import annotations

from typing import Any

from ..models import TransactionType, Wallet
from .mock_core import commit_block, make_transaction
from .mock_effects import LedgerEffects


def escrow_reward(
    ledger: Any, effects: LedgerEffects, run_id: str,
    to_wallet: str, amount: float, memo: str = "",
) -> dict[str, Any]:
    existing = (
        ledger._reward_escrows.get(f"released:{run_id}")
        or ledger._reward_escrows.get(f"escrowed:{run_id}")
    )
    if existing is not None:
        return existing
    wallet = ledger._wallets.get(to_wallet)
    if not wallet or amount <= 0:
        raise ValueError(f"Invalid reward escrow: wallet={to_wallet}, amount={amount}")
    escrow = make_transaction(
        ledger, effects, TransactionType.BOUNTY_ESCROW, None, None, amount, memo,
    )
    commit_block(ledger, effects, [escrow.tx_id])
    record = {
        "run_id": run_id,
        "wallet_id": to_wallet,
        "amount": amount,
        "escrow_tx_id": escrow.tx_id,
        "memo": memo,
        "status": "escrowed",
    }
    ledger._reward_escrows[f"escrowed:{run_id}"] = record
    effects.emit("blockchain.reward.escrowed", {
        "run_id": run_id, "entity_id": run_id, "wallet_id": to_wallet,
        "amount": amount, "escrow_tx_id": escrow.tx_id, "status": "escrowed",
    })
    return record


def release_reward(ledger: Any, effects: LedgerEffects, run_id: str) -> dict[str, Any]:
    record = ledger._reward_escrows.get(f"escrowed:{run_id}")
    if record is None:
        raise ValueError(f"No pending reward escrow for run: {run_id}")
    released = ledger._reward_escrows.get(f"released:{run_id}")
    if released is not None:
        return {**released, "status": "released", "already_released": True}
    wallet = ledger._wallets.get(record["wallet_id"])
    if wallet is None:
        wallet = Wallet(wallet_id=record["wallet_id"], owner_id=record["wallet_id"].removeprefix("wallet-"), balance=0.0)
        ledger._wallets[wallet.wallet_id] = wallet
        effects.emit("blockchain.wallet.created", {
            "wallet_id": wallet.wallet_id, "entity_id": wallet.wallet_id,
            "owner_id": wallet.owner_id, "balance": 0.0,
        })
    wallet.balance += record["amount"]
    effects.sync_wallet(wallet)
    tx = make_transaction(
        ledger, effects, TransactionType.BOUNTY_RELEASE, None, wallet.wallet_id,
        record["amount"], record["memo"] or f"reward release run {run_id}",
    )
    commit_block(ledger, effects, [tx.tx_id])
    final = {**record, "release_tx_id": tx.tx_id, "status": "released"}
    ledger._reward_escrows[f"released:{run_id}"] = final
    effects.emit("blockchain.reward.released", {
        "run_id": run_id, "entity_id": run_id, "wallet_id": wallet.wallet_id,
        "amount": record["amount"], "release_tx_id": tx.tx_id, "status": "released",
    })
    return final


def get_reward_escrow(ledger: Any, run_id: str) -> dict[str, Any] | None:
    return (
        ledger._reward_escrows.get(f"released:{run_id}")
        or ledger._reward_escrows.get(f"escrowed:{run_id}")
    )


__all__ = ["escrow_reward", "get_reward_escrow", "release_reward"]
