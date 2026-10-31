"""Bounty operations for the MockLedger facade."""
from __future__ import annotations

import uuid
from typing import Any

from ..models import Bounty, BountyStatus, Transaction, TransactionType
from .mock_core import commit_block, make_transaction
from .mock_effects import LedgerEffects


def post_bounty(ledger: Any, effects: LedgerEffects, poster_wallet: str, amount: float, description: str = "", criteria: dict | None = None) -> Bounty:
    poster = ledger._wallets.get(poster_wallet)
    if not poster or amount <= 0 or poster.balance < amount:
        raise ValueError(f"Invalid bounty: wallet={poster_wallet}, amount={amount}")
    poster.balance -= amount
    escrow = make_transaction(ledger, effects, TransactionType.BOUNTY_ESCROW, poster_wallet, None, amount, "escrow")
    commit_block(ledger, effects, [escrow.tx_id])
    bounty = Bounty(bounty_id=f"bounty-{uuid.uuid4().hex[:12]}", poster_wallet=poster_wallet, amount=amount, description=description, criteria=criteria or {}, escrow_tx_id=escrow.tx_id)
    ledger._bounties[bounty.bounty_id] = bounty
    effects.sync_wallet(poster)
    effects.sync_bounty(bounty)
    effects.emit("blockchain.bounty.posted", {"bounty_id": bounty.bounty_id, "entity_id": bounty.bounty_id, "amount": amount, "poster_wallet": poster_wallet, "escrow_tx_id": escrow.tx_id, "status": bounty.status.value})
    return bounty


def claim_bounty(ledger: Any, effects: LedgerEffects, bounty_id: str, claimer_wallet: str) -> Transaction:
    bounty = ledger._bounties.get(bounty_id)
    if not bounty:
        raise ValueError(f"Bounty not found: {bounty_id}")
    if bounty.status != BountyStatus.OPEN:
        raise ValueError(f"Bounty not open: {bounty.status}")
    claimer = ledger._wallets.get(claimer_wallet)
    if not claimer:
        raise ValueError(f"Claimer not found: {claimer_wallet}")
    claimer.balance += bounty.amount
    release = make_transaction(ledger, effects, TransactionType.BOUNTY_RELEASE, None, claimer_wallet, bounty.amount, f"bounty {bounty_id} claimed")
    commit_block(ledger, effects, [release.tx_id])
    bounty.status, bounty.claimer_wallet, bounty.release_tx_id = BountyStatus.CLAIMED, claimer_wallet, release.tx_id
    effects.sync_wallet(claimer)
    effects.sync_bounty(bounty)
    effects.emit("blockchain.bounty.claimed", {"bounty_id": bounty_id, "entity_id": bounty_id, "claimer_wallet": claimer_wallet, "amount": bounty.amount, "release_tx_id": release.tx_id, "status": bounty.status.value})
    return release


def cancel_bounty(ledger: Any, effects: LedgerEffects, bounty_id: str) -> Transaction:
    bounty = ledger._bounties.get(bounty_id)
    if not bounty or bounty.status != BountyStatus.OPEN:
        raise ValueError(f"Cannot cancel: {bounty_id}")
    poster = ledger._wallets.get(bounty.poster_wallet)
    if poster:
        poster.balance += bounty.amount
        effects.sync_wallet(poster)
    tx = make_transaction(ledger, effects, TransactionType.BOUNTY_RELEASE, None, bounty.poster_wallet, bounty.amount, f"cancel {bounty_id}")
    commit_block(ledger, effects, [tx.tx_id])
    bounty.status, bounty.release_tx_id = BountyStatus.CANCELLED, tx.tx_id
    effects.sync_bounty(bounty)
    effects.emit("blockchain.bounty.cancelled", {"bounty_id": bounty_id, "entity_id": bounty_id, "poster_wallet": bounty.poster_wallet, "amount": bounty.amount, "release_tx_id": tx.tx_id, "status": bounty.status.value})
    return tx
