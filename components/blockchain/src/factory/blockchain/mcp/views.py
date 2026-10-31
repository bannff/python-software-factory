"""MCP registration facade for Blockchain UI views."""
from __future__ import annotations

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic

from ..runtime.runtime import BlockchainRuntime
from .contracts.base import EmptyInput
from .contracts.views import (
    ActivityInput,
    ActivityOutput,
    DashboardSummaryOutput,
    EntityGraphContextInput,
    EntityGraphContextOutput,
    ViewsOutput,
)
from .dashboard_summary import (
    build_dashboard_summary,
    list_recent_activity,
    list_related_graph_entities,
)
from .view_payload import economy_views


def register(mcp: Any, runtime: BlockchainRuntime) -> None:
    """Register Blockchain view definitions."""

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=DashboardSummaryOutput)
    def blockchain_get_dashboard_summary() -> ToolResult[DashboardSummaryOutput]:
        """Return aggregate blockchain dashboard data."""
        return DashboardSummaryOutput.model_validate(build_dashboard_summary(runtime))

    @mcp.tool()
    @deterministic(input_model=ActivityInput, output_model=ActivityOutput)
    def blockchain_get_activity(
        tx_id: str = "", bounty_id: str = "", wallet_id: str = "", limit: int = 20,
    ) -> ToolResult[ActivityOutput]:
        """Return recent recorded ledger activity."""
        entries = list_recent_activity(limit, tx_id or None, bounty_id or None, wallet_id or None)
        return ActivityOutput(tx_id=tx_id, bounty_id=bounty_id, wallet_id=wallet_id, entries=entries, count=len(entries))

    @mcp.tool()
    @deterministic(input_model=EntityGraphContextInput, output_model=EntityGraphContextOutput)
    def blockchain_get_entity_graph_context(entity_id: str, limit: int = 12) -> ToolResult[EntityGraphContextOutput]:
        """Return related graph entities for a blockchain entity."""
        entries = list_related_graph_entities(limit=limit, entity_id=entity_id)
        return EntityGraphContextOutput(entity_id=entity_id, entries=entries, count=len(entries))

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ViewsOutput)
    def blockchain_get_views() -> ToolResult[ViewsOutput]:
        """Return UIView definitions for the Blockchain brick."""
        return ViewsOutput(views=economy_views())
