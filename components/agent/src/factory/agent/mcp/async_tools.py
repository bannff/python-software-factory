"""Non-blocking typed graph and swarm launch MCP tools."""
from __future__ import annotations

import asyncio
import threading
import uuid
from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import (
    ToolResult, envelope_updates_from_mapping, get_envelope, normalize_envelope,
    ok, operational,
)

from .contracts.execution import AsyncLaunchOutput, InvokeGraphInput, InvokeSwarmInput

if TYPE_CHECKING:
    from ..agent import SuperAgent


def _build_async_context(context: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(context or {})
    envelope = envelope_updates_from_mapping(get_envelope())
    envelope.update(envelope_updates_from_mapping(merged))
    merged.update(envelope)
    normalized = normalize_envelope(merged)
    if run_id := normalized.get("run_id"):
        normalized["workflow_run_id"] = run_id
    return normalized


def _thread(coro: Callable[[], Any], state: Any) -> None:
    def target() -> None:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(coro())
            loop.close()
        except Exception as error:
            state.status, state.error = "failed", str(error)
    threading.Thread(target=target, daemon=True).start()


def register(mcp: Any, agent: "SuperAgent", get_mcp_tools: Callable[[], Any]) -> None:
    """Register non-blocking invocation tools."""

    @mcp.tool()
    @operational(input_model=InvokeGraphInput, output_model=AsyncLaunchOutput)
    async def invoke_graph_async(
        graph_id: str, task: str, context: dict[str, Any] | None = None,
    ) -> ToolResult[AsyncLaunchOutput]:
        """Enroll a graph and return its durable Workflow run id/status."""
        from .tools import _launch_registered_graph

        ctx = _build_async_context(context)
        result = await _launch_registered_graph(
            agent, graph_id, task, ctx, launcher="invoke_graph_async",
            requested_run_key=ctx.get("run_id"),
        )
        success = result.get("success") is True
        return ok(AsyncLaunchOutput(
            success=success,
            workflow_id=str(result.get("run_id", "")),
            status=str(result.get("status", "failed")),
            error=None if success else str(result.get("error", "failed")),
            validation_errors=result.get("validation_errors"),
        ))

    @mcp.tool()
    @operational(input_model=InvokeSwarmInput, output_model=AsyncLaunchOutput)
    async def invoke_swarm_async(
        swarm_id: str, task: str, context: dict[str, Any] | None = None,
    ) -> ToolResult[AsyncLaunchOutput]:
        """Launch a swarm in a background thread and return a workflow id."""
        from ..server import WorkflowState
        config = agent.swarm_registry.get(swarm_id)
        if not config:
            return ok(AsyncLaunchOutput(
                success=False, workflow_id="", status="not_found", error="not_found",
            ))
        ctx = _build_async_context(context)
        workflow_id = ctx.get("run_id") or f"wf-{uuid.uuid4().hex[:12]}"
        state = agent.workflows[workflow_id] = WorkflowState(status="running")

        async def run() -> None:
            from ..runtime.coordination import execute_registered
            state.result = await execute_registered(config, task, ctx)
            state.status = str(state.result.get("status", "failed"))

        _thread(run, state)
        return ok(AsyncLaunchOutput(
            success=True, workflow_id=workflow_id, status="running",
        ))
