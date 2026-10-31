"""DTOs for operational Blockchain MCP tools."""
from __future__ import annotations

from .base import DTO, JsonObject
from .ledger import BountiesOutput, BountyOutput, OperationOutput, TransactionOutput, WalletOutput


class MyWalletOutput(WalletOutput):
    pass


class CreateWalletInput(DTO):
    owner_id: str
    initial_balance: float = 0


class CreateWalletOutput(WalletOutput):
    pass


class TransferInput(DTO):
    from_wallet: str
    to_wallet: str
    amount: float
    memo: str = ""


class MintInput(DTO):
    to_wallet: str
    amount: float
    memo: str = ""


class RewardEscrowInput(DTO):
    run_id: str
    to_wallet: str
    amount: float
    memo: str = ""


class RewardReleaseInput(DTO):
    run_id: str


class PostBountyInput(DTO):
    poster_wallet: str
    amount: float
    description: str = ""
    criteria: JsonObject | None = None


class BountyIdInput(DTO):
    bounty_id: str


class ClaimBountyInput(BountyIdInput):
    claimer_wallet: str


class ListBountiesInput(DTO):
    status: str | None = None
    limit: int = 50


class ReconcileInput(DTO):
    wallet_id: str


class ReconcileOutput(OperationOutput):
    wallet_id: str | None = None
    expected_balance: float | None = None
    actual_balance: float | None = None


__all__ = [
    "BountiesOutput", "BountyIdInput", "BountyOutput", "ClaimBountyInput",
    "CreateWalletInput", "CreateWalletOutput", "ListBountiesInput", "MintInput",
    "MyWalletOutput", "PostBountyInput", "ReconcileInput", "ReconcileOutput",
    "TransactionOutput", "TransferInput",
]
