"""Typed MCP tool for Workflow-owned background persona launch."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, fail, ok, operational

from .contracts.spawn_background import (
    SpawnBackgroundInput, SpawnBackgroundOutput,
    SteerBackgroundInput, SteerBackgroundOutput,
)
from ..runtime.background import (
    BackgroundLaunchError, launch_background, steer_background,
)

if TYPE_CHECKING:
    from ..agent import SuperAgent


def register(mcp: Any, agent: "SuperAgent") -> None:
    @mcp.tool(name="spawn_background")
    @operational(
        input_model=SpawnBackgroundInput,
        output_model=SpawnBackgroundOutput,
        idempotent=False,
    )
    async def spawn_background(
        agent_id: str, task: str, context: dict[str, str] | None = None,
        launch_id: str | None = None,
        output_schema: str | None = None, delivery_mode: str = "origin",
        loop_id: str | None = None, loop_cycle: int | None = None,
    ) -> ToolResult[SpawnBackgroundOutput]:
        """Launch one registered persona as a durable Workflow attempt."""
        try:
            result = await launch_background(
                agent.agent_registry, agent_id, task, launch_id, context,
                output_schema, delivery_mode, loop_id, loop_cycle,
            )
            return ok(SpawnBackgroundOutput.model_validate(result))
        except BackgroundLaunchError as exc:
            return fail(exc.code)

    @mcp.tool(name="steer_background")
    @operational(
        input_model=SteerBackgroundInput,
        output_model=SteerBackgroundOutput,
        idempotent=False,
    )
    async def steer_background_tool(
        run_id: str, send_id: str, content: str,
    ) -> ToolResult[SteerBackgroundOutput]:
        """Steer one currently running background Agent attempt."""
        try:
            result = await steer_background(run_id, send_id, content)
            return ok(SteerBackgroundOutput.model_validate(result))
        except BackgroundLaunchError as exc:
            return fail(exc.code)


__all__ = ["register"]
