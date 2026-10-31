"""DTOs for authoring Blockchain MCP tools."""
from __future__ import annotations

from .base import DTO
from .ledger import WalletData


class AuthoringStatusOutput(DTO):
    enabled: bool


class SeedEconomyInput(DTO):
    agent_count: int = 5
    initial_balance: float = 1000.0


class SeedEconomyOutput(DTO):
    ok: bool
    wallets_created: int = 0
    wallets: list[WalletData] = []
    error: str | None = None
