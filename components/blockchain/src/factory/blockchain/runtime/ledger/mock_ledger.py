"""In-memory mock ledger facade for local development and tests."""
from __future__ import annotations

from typing import Any

from .. import event_emitter
from ..graph_sync import sync_block, sync_bounty, sync_transaction, sync_wallet
from ..models import Block, Bounty, ChainInfo, Transaction, Wallet
from .mock_bounties import cancel_bounty, claim_bounty, post_bounty
from .mock_core import TREASURY_ID, commit_block, initialize, make_transaction, reconcile, verify
from .mock_effects import LedgerEffects
from .mock_rewards import escrow_reward as _escrow_reward
from .mock_rewards import get_reward_escrow as _get_reward_escrow
from .mock_rewards import release_reward as _release_reward
from .mock_wallets import create_wallet, mint, transfer


class MockLedger:
    """In-memory ledger implementing LedgerPort.

    The imported sync functions and ``event_emitter`` intentionally remain module
    globals: existing tests and local integrations monkeypatch this module's seams.
    Helpers receive them as effects for each operation rather than capturing them.
    """

    def __init__(self, total_supply: float = 1_000_000.0) -> None:
        self._wallets: dict[str, Wallet] = {}
        self._transactions: dict[str, Transaction] = {}
        self._blocks: list[Block] = []
        self._bounties: dict[str, Bounty] = {}
        self._reward_escrows: dict[str, dict[str, Any]] = {}
        self._total_supply = total_supply
        self._init_genesis(total_supply)

    @staticmethod
    def _effects() -> LedgerEffects:
        return LedgerEffects(sync_wallet, sync_transaction, sync_block, sync_bounty, event_emitter.emit)

    def _init_genesis(self, supply: float) -> None:
        initialize(self, self._effects(), supply)

    def _make_tx(self, tx_type, from_w: str | None, to_w: str | None, amount: float, memo: str) -> Transaction:
        return make_transaction(self, self._effects(), tx_type, from_w, to_w, amount, memo)

    def _commit_block(self, tx_ids: list[str]) -> Block:
        return commit_block(self, self._effects(), tx_ids)

    def create_wallet(self, owner_id: str, initial_balance: float = 0) -> Wallet:
        return create_wallet(self, self._effects(), owner_id, initial_balance)

    def get_wallet(self, wallet_id: str) -> Wallet | None:
        return self._wallets.get(wallet_id)

    def transfer(self, from_wallet: str, to_wallet: str, amount: float, memo: str = "") -> Transaction:
        return transfer(self, self._effects(), from_wallet, to_wallet, amount, memo)

    def get_balance(self, wallet_id: str) -> float:
        wallet = self._wallets.get(wallet_id)
        if not wallet:
            raise ValueError(f"Wallet not found: {wallet_id}")
        return wallet.balance

    def get_transactions(self, wallet_id: str | None = None, limit: int = 50) -> list[Transaction]:
        transactions = list(self._transactions.values())
        if wallet_id:
            transactions = [tx for tx in transactions if tx.from_wallet == wallet_id or tx.to_wallet == wallet_id]
        return sorted(transactions, key=lambda tx: tx.created_at, reverse=True)[:limit]

    def mint(self, to_wallet: str, amount: float, memo: str = "") -> Transaction:
        return mint(self, self._effects(), to_wallet, amount, memo)

    def escrow_reward(self, run_id: str, to_wallet: str, amount: float, memo: str = "") -> dict[str, Any]:
        return _escrow_reward(self, self._effects(), run_id, to_wallet, amount, memo)

    def release_reward(self, run_id: str) -> dict[str, Any]:
        return _release_reward(self, self._effects(), run_id)

    def get_reward_escrow(self, run_id: str) -> dict[str, Any] | None:
        return _get_reward_escrow(self, run_id)

    def post_bounty(self, poster_wallet: str, amount: float, description: str = "", criteria: dict | None = None) -> Bounty:
        return post_bounty(self, self._effects(), poster_wallet, amount, description, criteria)

    def claim_bounty(self, bounty_id: str, claimer_wallet: str) -> Transaction:
        return claim_bounty(self, self._effects(), bounty_id, claimer_wallet)

    def get_bounty(self, bounty_id: str) -> Bounty | None:
        return self._bounties.get(bounty_id)

    def cancel_bounty(self, bounty_id: str) -> Transaction:
        return cancel_bounty(self, self._effects(), bounty_id)

    def list_bounties(self, status: str | None = None, limit: int = 50) -> list[Bounty]:
        bounties = [bounty for bounty in self._bounties.values() if not status or bounty.status == status]
        return sorted(bounties, key=lambda bounty: bounty.created_at, reverse=True)[:limit]

    def get_block(self, height: int) -> Block | None:
        return self._blocks[height] if 0 <= height < len(self._blocks) else None

    def get_chain_info(self) -> ChainInfo:
        return ChainInfo(height=len(self._blocks), total_supply=self._total_supply, wallet_count=len(self._wallets), tx_count=len(self._transactions), bounty_count=len(self._bounties), genesis_hash=self._blocks[0].hash if self._blocks else "")

    def verify_chain(self) -> dict[str, Any]:
        return verify(self)

    def reconcile(self, wallet_id: str) -> dict[str, Any]:
        return reconcile(self, wallet_id)

    def health_check(self) -> dict[str, Any]:
        return {"healthy": True, "provider": "mock_ledger", "chain_height": len(self._blocks)}


__all__ = ["MockLedger", "TREASURY_ID", "sync_block", "sync_bounty", "sync_transaction", "sync_wallet", "event_emitter"]
