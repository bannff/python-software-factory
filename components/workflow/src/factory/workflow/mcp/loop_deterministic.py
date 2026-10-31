"""Typed deterministic MCP tools for Workflow loop reads."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import ToolResult, deterministic

from .contracts.loops import (
    ListLoopsInput, LoopCycleOutput, LoopCycleRefInput,
    LoopOutput, LoopRefInput, LoopsOutput,
)
from .loop_support import authority


def register(mcp: Any, runtime: Any) -> None:
    @mcp.tool(name="workflow.get_loop")
    @deterministic(input_model=LoopRefInput, output_model=LoopOutput)
    def get_loop(loop_id: str, envelope: dict | None = None) -> ToolResult[LoopOutput]:
        return LoopOutput(loop=runtime.get_loop(loop_id, authority(envelope)))

    @mcp.tool(name="workflow.list_loops")
    @deterministic(input_model=ListLoopsInput, output_model=LoopsOutput)
    def list_loops(
        limit: int = 100, envelope: dict | None = None,
    ) -> ToolResult[LoopsOutput]:
        return LoopsOutput(loops=runtime.list_loops(authority(envelope), limit))

    @mcp.tool(name="workflow.get_loop_cycle")
    @deterministic(input_model=LoopCycleRefInput, output_model=LoopCycleOutput)
    def get_loop_cycle(
        loop_id: str, cycle: int, envelope: dict | None = None,
    ) -> ToolResult[LoopCycleOutput]:
        return LoopCycleOutput(cycle=runtime.get_loop_cycle(
            loop_id, cycle, authority(envelope),
        ))


__all__ = ["register"]
