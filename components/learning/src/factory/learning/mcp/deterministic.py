"""Deterministic (read-only) MCP tools for the learning brick."""

from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.decorators import deterministic
from factory.mcp_utils.registration import typed_tool
from factory.mcp_utils.runtime.tool_result import ToolResult, ok

from .contracts import EmptyInput, RewardSourcesOutput

if TYPE_CHECKING:
    from ..runtime.runtime import LearningRuntime


def register(mcp: Any, get_runtime: Callable[[], "LearningRuntime"]) -> None:
    """Register deterministic tools with the strict MCP boundary."""

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=RewardSourcesOutput)
    def learning_list_reward_sources() -> ToolResult[RewardSourcesOutput]:
        """List registered source ids in a successful typed v1 envelope."""
        return ok(RewardSourcesOutput(source_ids=get_runtime().registry.source_ids()))
