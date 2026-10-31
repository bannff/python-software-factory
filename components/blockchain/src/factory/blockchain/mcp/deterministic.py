"""Typed deterministic MCP tools for Blockchain."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic

from .contracts.base import EmptyInput
from .contracts.deterministic import (
    BalanceOutput, BlockOutput, CapabilitiesOutput, ConfigSchemaOutput,
    GetBlockInput, GetWalletOutput, HealthOutput, ListTransactionsInput,
    VerifyChainOutput, WalletIdInput,
)
from .contracts.ledger import ChainInfoOutput, TransactionsOutput

if TYPE_CHECKING:
    from ..runtime.runtime import BlockchainRuntime


def register(mcp: Any, get_runtime: Callable[[], "BlockchainRuntime"]) -> None:
    """Register deterministic tools with strict public contracts."""

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def blockchain_get_capabilities() -> ToolResult[CapabilitiesOutput]:
        return CapabilitiesOutput.model_validate(get_runtime().capabilities())

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def blockchain_health_check() -> ToolResult[HealthOutput]:
        return HealthOutput.model_validate(get_runtime().health_check())

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def blockchain_describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        return ConfigSchemaOutput.model_validate(get_runtime().config_schema())

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ChainInfoOutput)
    def blockchain_get_chain_info() -> ToolResult[ChainInfoOutput]:
        return ChainInfoOutput.model_validate(get_runtime().get_ledger().get_chain_info().model_dump(mode="json"))

    @mcp.tool()
    @deterministic(input_model=WalletIdInput, output_model=BalanceOutput)
    def blockchain_get_balance(wallet_id: str) -> ToolResult[BalanceOutput]:
        try:
            return BalanceOutput(wallet_id=wallet_id, balance=get_runtime().get_ledger().get_balance(wallet_id))
        except ValueError as exc:
            return BalanceOutput(wallet_id=wallet_id, balance=None, found=False, error=str(exc))

    @mcp.tool()
    @deterministic(input_model=WalletIdInput, output_model=GetWalletOutput)
    def blockchain_get_wallet(wallet_id: str) -> ToolResult[GetWalletOutput]:
        wallet = get_runtime().get_ledger().get_wallet(wallet_id)
        if wallet is None:
            return GetWalletOutput(wallet_id=wallet_id, owner_id="", balance=0, created_at="", found=False, error="not_found")
        return GetWalletOutput.model_validate(wallet.model_dump(mode="json"))

    @mcp.tool()
    @deterministic(input_model=ListTransactionsInput, output_model=TransactionsOutput)
    def blockchain_list_transactions(wallet_id: str | None = None, limit: int = 50) -> ToolResult[TransactionsOutput]:
        txs = get_runtime().get_ledger().get_transactions(wallet_id, limit)
        return TransactionsOutput(transactions=[item.model_dump(mode="json") for item in txs], count=len(txs))

    @mcp.tool()
    @deterministic(input_model=GetBlockInput, output_model=BlockOutput)
    def blockchain_get_block(height: int) -> ToolResult[BlockOutput]:
        block = get_runtime().get_ledger().get_block(height)
        if block is None:
            return BlockOutput(found=False, error="not_found")
        return BlockOutput.model_validate(block.model_dump(mode="json"))

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=VerifyChainOutput)
    def blockchain_verify_chain() -> ToolResult[VerifyChainOutput]:
        return VerifyChainOutput.model_validate(get_runtime().get_ledger().verify_chain())
