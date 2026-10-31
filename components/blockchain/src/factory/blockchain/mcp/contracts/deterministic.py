"""DTOs for deterministic Blockchain MCP tools."""
from __future__ import annotations

from .base import DTO, JsonObject
from .ledger import ChainInfoOutput, TransactionsOutput, WalletOutput


class CapabilitiesOutput(DTO):
    name: str
    version: str
    features: list[str]
    backends: list[str]


class HealthOutput(DTO):
    healthy: bool
    provider: str
    chain_height: int = 0


class ConfigSchemaOutput(DTO):
    type: str
    properties: JsonObject


class WalletIdInput(DTO):
    wallet_id: str


class BalanceOutput(DTO):
    wallet_id: str
    balance: float | None = None
    found: bool = True
    error: str | None = None


class GetWalletOutput(WalletOutput):
    pass


class ListTransactionsInput(DTO):
    wallet_id: str | None = None
    limit: int = 50


class GetBlockInput(DTO):
    height: int


class BlockOutput(DTO):
    found: bool = True
    height: int | None = None
    hash: str | None = None
    prev_hash: str | None = None
    merkle_root: str | None = None
    tx_ids: list[str] | None = None
    timestamp: str | None = None
    error: str | None = None


class VerifyChainOutput(DTO):
    valid: bool
    error: str | None = None


__all__ = [
    "BalanceOutput", "BlockOutput", "CapabilitiesOutput", "ChainInfoOutput",
    "ConfigSchemaOutput", "GetBlockInput", "GetWalletOutput", "HealthOutput",
    "ListTransactionsInput", "TransactionsOutput", "VerifyChainOutput", "WalletIdInput",
]
