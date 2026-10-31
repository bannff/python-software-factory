"""Typed operational MCP tools for Blockchain."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from typing import Any
from factory.mcp_utils.interface import ToolResult, operational

from .contracts.base import EmptyInput
from .contracts.ledger import BountiesOutput, BountyOutput, TransactionOutput
from .contracts.operational import (
    BountyIdInput, ClaimBountyInput, CreateWalletInput,
    CreateWalletOutput, ListBountiesInput, MintInput, MyWalletOutput,
    PostBountyInput, ReconcileInput, ReconcileOutput, RewardEscrowInput,
    RewardReleaseInput, TransferInput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import BlockchainRuntime


def _my_wallet(get_runtime: Callable[[], "BlockchainRuntime"]) -> str:
    from ..runtime.auto_wallet import get_or_create_wallet
    return get_or_create_wallet(get_runtime().get_ledger())


def _transaction(call: Callable[[], object]) -> TransactionOutput:
    try:
        return TransactionOutput.model_validate(call().model_dump(mode="json"))
    except ValueError as exc:
        return TransactionOutput(success=False, error=str(exc))


def _bounty(call: Callable[[], object]) -> BountyOutput:
    try:
        return BountyOutput.model_validate(call().model_dump(mode="json"))
    except ValueError as exc:
        return BountyOutput(success=False, error=str(exc))


def register(mcp: Any, get_runtime: Callable[[], "BlockchainRuntime"]) -> None:
    """Register operational tools with strict public contracts."""

    @mcp.tool()
    @operational(input_model=EmptyInput, output_model=MyWalletOutput)
    def blockchain_my_wallet() -> ToolResult[MyWalletOutput]:
        wallet = get_runtime().get_ledger().get_wallet(_my_wallet(get_runtime))
        if wallet is None:
            return MyWalletOutput(wallet_id="", owner_id="", balance=0, created_at="", found=False, error="wallet_creation_failed")
        return MyWalletOutput.model_validate(wallet.model_dump(mode="json"))

    @mcp.tool()
    @operational(input_model=CreateWalletInput, output_model=CreateWalletOutput)
    def blockchain_create_wallet(owner_id: str, initial_balance: float = 0) -> ToolResult[CreateWalletOutput]:
        try:
            wallet = get_runtime().get_ledger().create_wallet(owner_id, initial_balance)
            return CreateWalletOutput.model_validate(wallet.model_dump(mode="json"))
        except ValueError as exc:
            return CreateWalletOutput(wallet_id="", owner_id=owner_id, balance=0, created_at="", found=False, error=str(exc))

    @mcp.tool()
    @operational(input_model=TransferInput, output_model=TransactionOutput)
    def blockchain_transfer(from_wallet: str, to_wallet: str, amount: float, memo: str = "") -> ToolResult[TransactionOutput]:
        return _transaction(lambda: get_runtime().get_ledger().transfer(from_wallet, to_wallet, amount, memo))

    @mcp.tool()
    @operational(input_model=MintInput, output_model=TransactionOutput)
    def blockchain_mint(to_wallet: str, amount: float, memo: str = "") -> ToolResult[TransactionOutput]:
        return _transaction(lambda: get_runtime().get_ledger().mint(to_wallet, amount, memo))

    @mcp.tool()
    @operational(input_model=RewardEscrowInput, output_model=TransactionOutput)
    def blockchain_reward_escrow(run_id: str, to_wallet: str, amount: float, memo: str = "") -> ToolResult[TransactionOutput]:
        """Park a pending reward payout keyed by run_id (released by the eval projection)."""
        try:
            record = get_runtime().get_ledger().escrow_reward(run_id, to_wallet, amount, memo)
        except ValueError as exc:
            return TransactionOutput(success=False, error=str(exc))
        return TransactionOutput(tx_id=record["escrow_tx_id"], tx_type="bounty_escrow", to_wallet=None, amount=amount, memo=memo, status="escrowed")

    @mcp.tool()
    @operational(input_model=RewardReleaseInput, output_model=TransactionOutput)
    def blockchain_reward_release(run_id: str) -> ToolResult[TransactionOutput]:
        """Credit an escrowed reward (BOUNTY_RELEASE); idempotent per run_id."""
        try:
            record = get_runtime().get_ledger().release_reward(run_id)
        except ValueError as exc:
            return TransactionOutput(success=False, error=str(exc))
        return TransactionOutput(tx_id=record["release_tx_id"], tx_type="bounty_release", to_wallet=record["wallet_id"], amount=float(record["amount"]), memo=record.get("memo", ""), status="released")

    @mcp.tool()
    @operational(input_model=PostBountyInput, output_model=BountyOutput)
    def blockchain_post_bounty(poster_wallet: str, amount: float, description: str = "", criteria: dict | None = None) -> ToolResult[BountyOutput]:
        return _bounty(lambda: get_runtime().get_ledger().post_bounty(poster_wallet, amount, description, criteria))

    @mcp.tool()
    @operational(input_model=ClaimBountyInput, output_model=TransactionOutput)
    def blockchain_claim_bounty(bounty_id: str, claimer_wallet: str) -> ToolResult[TransactionOutput]:
        return _transaction(lambda: get_runtime().get_ledger().claim_bounty(bounty_id, claimer_wallet))

    @mcp.tool()
    @operational(input_model=BountyIdInput, output_model=TransactionOutput)
    def blockchain_cancel_bounty(bounty_id: str) -> ToolResult[TransactionOutput]:
        return _transaction(lambda: get_runtime().get_ledger().cancel_bounty(bounty_id))

    @mcp.tool()
    @operational(input_model=ListBountiesInput, output_model=BountiesOutput)
    def blockchain_list_bounties(status: str | None = None, limit: int = 50) -> ToolResult[BountiesOutput]:
        bounties = get_runtime().get_ledger().list_bounties(status, limit)
        return BountiesOutput(bounties=[item.model_dump(mode="json") for item in bounties], count=len(bounties))

    @mcp.tool()
    @operational(input_model=ReconcileInput, output_model=ReconcileOutput)
    def blockchain_reconcile(wallet_id: str) -> ToolResult[ReconcileOutput]:
        try:
            return ReconcileOutput.model_validate(get_runtime().get_ledger().reconcile(wallet_id))
        except ValueError as exc:
            return ReconcileOutput(success=False, wallet_id=wallet_id, error=str(exc))
