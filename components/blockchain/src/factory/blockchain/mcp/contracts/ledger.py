"""JSON-safe ledger DTOs shared by Blockchain MCP tools."""
from __future__ import annotations

from .base import DTO, JsonObject


class WalletData(DTO):
    wallet_id: str
    owner_id: str
    balance: float
    created_at: str


class WalletOutput(WalletData):
    found: bool = True
    error: str | None = None


class TransactionOutput(DTO):
    success: bool = True
    tx_id: str | None = None
    tx_type: str | None = None
    from_wallet: str | None = None
    to_wallet: str | None = None
    amount: float | None = None
    memo: str | None = None
    status: str | None = None
    block_height: int | None = None
    created_at: str | None = None
    error: str | None = None


class BountyOutput(DTO):
    success: bool = True
    bounty_id: str | None = None
    poster_wallet: str | None = None
    amount: float | None = None
    description: str | None = None
    criteria: JsonObject | None = None
    status: str | None = None
    claimer_wallet: str | None = None
    escrow_tx_id: str | None = None
    release_tx_id: str | None = None
    created_at: str | None = None
    error: str | None = None


class OperationOutput(DTO):
    success: bool = True
    error: str | None = None


class ChainInfoOutput(DTO):
    height: int
    total_supply: float
    wallet_count: int
    tx_count: int
    bounty_count: int
    genesis_hash: str


class TransactionsOutput(DTO):
    transactions: list[TransactionOutput]
    count: int


class BountiesOutput(DTO):
    bounties: list[BountyOutput]
    count: int
