"""Typed authoring MCP tools for Blockchain."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Callable

from typing import Any
from factory.mcp_utils.interface import ToolResult, authoring

from .contracts.authoring import AuthoringStatusOutput, SeedEconomyInput, SeedEconomyOutput
from .contracts.base import EmptyInput

if TYPE_CHECKING:
    from ..runtime.runtime import BlockchainRuntime


def _is_authoring_enabled() -> bool:
    return os.environ.get("BLOCKCHAIN_ENABLE_AUTHORING_TOOLS") == "1"


def register(mcp: Any, get_runtime: Callable[[], "BlockchainRuntime"]) -> None:
    """Register authoring tools with strict public contracts."""

    @mcp.tool()
    @authoring(input_model=EmptyInput, output_model=AuthoringStatusOutput)
    def blockchain_authoring_get_status() -> ToolResult[AuthoringStatusOutput]:
        """Get authoring status."""
        return AuthoringStatusOutput(enabled=_is_authoring_enabled())

    @mcp.tool()
    @authoring(input_model=SeedEconomyInput, output_model=SeedEconomyOutput)
    def blockchain_authoring_seed_economy(agent_count: int = 5, initial_balance: float = 1000.0) -> ToolResult[SeedEconomyOutput]:
        """Create local development wallets when authoring is enabled."""
        if not _is_authoring_enabled():
            return SeedEconomyOutput(ok=False, error="authoring_disabled")
        wallets = [get_runtime().get_ledger().create_wallet(f"agent-{index:03d}", initial_balance).model_dump(mode="json") for index in range(agent_count)]
        return SeedEconomyOutput(ok=True, wallets_created=len(wallets), wallets=wallets)
