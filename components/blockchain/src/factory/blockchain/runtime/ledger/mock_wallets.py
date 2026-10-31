"""Wallet and transaction operations for the MockLedger facade."""
from __future__ import annotations

from typing import Any

from ..models import Transaction, TransactionType, Wallet
from .mock_core import TREASURY_ID, commit_block, make_transaction
from .mock_effects import LedgerEffects


def create_wallet(ledger: Any, effects: LedgerEffects, owner_id: str, initial_balance: float = 0) -> Wallet:
    wallet_id = f"wallet-{owner_id}"
    if wallet_id in ledger._wallets:
        raise ValueError(f"Wallet already exists: {wallet_id}")
    ledger._wallets[wallet_id] = Wallet(wallet_id=wallet_id, owner_id=owner_id, balance=0.0)
    effects.sync_wallet(ledger._wallets[wallet_id])
    effects.emit("blockchain.wallet.created", {"wallet_id": wallet_id, "entity_id": wallet_id, "owner_id": owner_id, "balance": 0.0})
    if initial_balance > 0:
        transfer(ledger, effects, TREASURY_ID, wallet_id, initial_balance, "initial allocation")
    return ledger._wallets[wallet_id]


def transfer(ledger: Any, effects: LedgerEffects, from_wallet: str, to_wallet: str, amount: float, memo: str = "") -> Transaction:
    sender, receiver = ledger._wallets.get(from_wallet), ledger._wallets.get(to_wallet)
    if not sender:
        raise ValueError(f"Sender not found: {from_wallet}")
    if not receiver:
        raise ValueError(f"Receiver not found: {to_wallet}")
    if amount <= 0 or sender.balance < amount:
        raise ValueError(f"Invalid transfer: balance={sender.balance}, amount={amount}")
    sender.balance -= amount
    receiver.balance += amount
    effects.sync_wallet(sender)
    effects.sync_wallet(receiver)
    tx = make_transaction(ledger, effects, TransactionType.TRANSFER, from_wallet, to_wallet, amount, memo)
    commit_block(ledger, effects, [tx.tx_id])
    effects.emit("blockchain.tx.committed", {"tx_id": tx.tx_id, "entity_id": tx.tx_id, "tx_type": tx.tx_type.value, "amount": amount, "from_wallet": from_wallet, "to_wallet": to_wallet, "memo": memo, "block_height": tx.block_height})
    return tx


def mint(ledger: Any, effects: LedgerEffects, to_wallet: str, amount: float, memo: str = "") -> Transaction:
    receiver = ledger._wallets.get(to_wallet)
    if not receiver:
        raise ValueError(f"Wallet not found: {to_wallet}")
    if amount <= 0:
        raise ValueError("Amount must be positive")
    receiver.balance += amount
    effects.sync_wallet(receiver)
    tx = make_transaction(ledger, effects, TransactionType.MINT, None, to_wallet, amount, memo)
    commit_block(ledger, effects, [tx.tx_id])
    effects.emit("blockchain.tx.committed", {"tx_id": tx.tx_id, "entity_id": tx.tx_id, "tx_type": tx.tx_type.value, "amount": amount, "to_wallet": to_wallet, "memo": memo, "block_height": tx.block_height})
    return tx
