"""Core state transitions shared by the MockLedger facade methods."""
from __future__ import annotations

import uuid
from typing import Any

from ..models import Block, Transaction, TransactionStatus, TransactionType, Wallet
from .chain_ops import _GENESIS_PREV, make_block, verify_blocks
from .mock_effects import LedgerEffects

TREASURY_ID = "wallet-treasury"


def initialize(ledger: Any, effects: LedgerEffects, supply: float) -> None:
    treasury = Wallet(wallet_id=TREASURY_ID, owner_id="treasury", balance=supply)
    ledger._wallets[TREASURY_ID] = treasury
    effects.sync_wallet(treasury)
    mint = make_transaction(ledger, effects, TransactionType.MINT, None, TREASURY_ID, supply, "genesis mint")
    commit_block(ledger, effects, [mint.tx_id])


def make_transaction(
    ledger: Any, effects: LedgerEffects, tx_type: TransactionType, from_wallet: str | None,
    to_wallet: str | None, amount: float, memo: str,
) -> Transaction:
    tx = Transaction(tx_id=f"tx-{uuid.uuid4().hex[:12]}", tx_type=tx_type, from_wallet=from_wallet, to_wallet=to_wallet, amount=amount, memo=memo, status=TransactionStatus.COMMITTED)
    ledger._transactions[tx.tx_id] = tx
    effects.sync_transaction(tx)
    return tx


def commit_block(ledger: Any, effects: LedgerEffects, tx_ids: list[str]) -> Block:
    previous = ledger._blocks[-1].hash if ledger._blocks else _GENESIS_PREV
    block = make_block(len(ledger._blocks), previous, tx_ids)
    ledger._blocks.append(block)
    for tx_id in tx_ids:
        if tx_id in ledger._transactions:
            ledger._transactions[tx_id].block_height = block.height
            effects.sync_transaction(ledger._transactions[tx_id])
    effects.sync_block(block)
    return block


def reconcile(ledger: Any, wallet_id: str) -> dict[str, Any]:
    wallet = ledger._wallets.get(wallet_id)
    if not wallet:
        raise ValueError(f"Wallet not found: {wallet_id}")
    computed = sum((tx.amount if tx.to_wallet == wallet_id else 0) - (tx.amount if tx.from_wallet == wallet_id else 0) for tx in ledger._transactions.values())
    drift = abs(wallet.balance - computed)
    if drift > 0.001:
        wallet.balance = computed
    return {"wallet_id": wallet_id, "stored": wallet.balance, "computed": computed, "drift": drift}


def verify(ledger: Any) -> dict[str, Any]:
    return verify_blocks(ledger._blocks)
