"""Typed operational MCP tools for durable Workflow loops."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import ToolResult, operational

from ..runtime.loop_models import LoopState
from .contracts.loops import LoopOutput, LoopRevisionInput, StartLoopInput
from .loop_support import authority, resolve_origin


def register(mcp: Any, runtime: Any) -> None:
    @mcp.tool(name="workflow.start_loop")
    @operational(input_model=StartLoopInput, output_model=LoopOutput)
    async def start_loop(
        kind: str, agent_id: str, objective: str, cycle_instructions: str,
        interval_seconds: int = 300, max_cycles: int = 24,
        max_runtime_seconds: int = 0, loop_id: str | None = None,
        envelope: dict | None = None,
    ) -> ToolResult[LoopOutput]:
        context = authority(envelope)
        origin = await resolve_origin(context)
        loop = runtime.start_loop(
            kind=kind, agent_id=agent_id, objective=objective,
            cycle_instructions=cycle_instructions,
            interval_seconds=interval_seconds, max_cycles=max_cycles,
            max_runtime_seconds=max_runtime_seconds, loop_id=loop_id,
            origin_session_id=origin, envelope=context,
        )
        return LoopOutput(loop=loop)

    def transition(name: str, state: LoopState):
        @mcp.tool(name=name)
        @operational(input_model=LoopRevisionInput, output_model=LoopOutput)
        def tool(
            loop_id: str, expected_revision: int,
            envelope: dict | None = None,
        ) -> ToolResult[LoopOutput]:
            return LoopOutput(loop=runtime.transition_loop(
                loop_id, expected_revision, state, authority(envelope),
            ))
        return tool

    transition("workflow.pause_loop", LoopState.PAUSED)
    transition("workflow.resume_loop", LoopState.ACTIVE)
    transition("workflow.stop_loop", LoopState.STOPPED)


__all__ = ["register"]
