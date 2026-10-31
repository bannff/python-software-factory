"""Typed MCP tools for bounded registered-persona execution."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, ok, operational

from .contracts.spawn import (
    SpawnGraphInput, SpawnOutput, SpawnSubagentInput, SpawnSwarmInput,
)
from ..runtime.spawn import SpawnCoordinator

if TYPE_CHECKING:
    from ..agent import SuperAgent


def register(mcp: Any, agent: "SuperAgent") -> None:
    """Register canonical local names; aggregation exposes ``agent_spawn_*``."""
    coordinator = SpawnCoordinator(agent.agent_registry)

    @mcp.tool(name="spawn_subagent")
    @operational(input_model=SpawnSubagentInput, output_model=SpawnOutput)
    async def spawn_subagent(
        agent_id: str, task: str, context: dict[str, Any] | None = None,
    ) -> ToolResult[SpawnOutput]:
        """Execute one registered persona in one bounded runtime invocation."""
        return ok(SpawnOutput.model_validate(
            await coordinator.subagent(agent_id, task, context),
        ))

    @mcp.tool(name="spawn_swarm")
    @operational(input_model=SpawnSwarmInput, output_model=SpawnOutput)
    async def spawn_swarm(
        agent_ids: list[str], task: str, context: dict[str, Any] | None = None,
    ) -> ToolResult[SpawnOutput]:
        """Execute two or more registered personas as an ordered bounded graph."""
        return ok(SpawnOutput.model_validate(
            await coordinator.swarm(agent_ids, task, context),
        ))

    @mcp.tool(name="spawn_graph")
    @operational(input_model=SpawnGraphInput, output_model=SpawnOutput)
    async def spawn_graph(
        agent_ids: list[str], edges: list[dict[str, str]], task: str,
        context: dict[str, Any] | None = None,
    ) -> ToolResult[SpawnOutput]:
        """Execute registered personas through a caller-declared directed DAG."""
        return ok(SpawnOutput.model_validate(
            await coordinator.graph(agent_ids, edges, task, context),
        ))


__all__ = ["register"]
