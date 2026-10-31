"""Canonical typed MCP tools for SuperAgent."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, deterministic, ok, operational

from .contracts.discovery import (
    AgentRegistryOutput, CapabilitiesOutput, EmptyInput, GraphRegistryOutput,
    HealthOutput, SwarmRegistryOutput, WorkflowStatusInput, WorkflowStatusOutput,
)
from .contracts.execution import (
    CancelWorkflowInput, CancelWorkflowOutput, ExecutionOutput, InvokeGraphInput,
    InvokeSwarmInput, ReasonInput,
)

if TYPE_CHECKING:
    from ..agent import SuperAgent


def register(mcp: Any, agent: "SuperAgent") -> None:
    """Register typed discovery and reasoning tools."""

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def get_capabilities() -> ToolResult[CapabilitiesOutput]:
        """List all available tools, swarms, and graphs."""
        return ok(CapabilitiesOutput.model_validate(agent.get_capabilities()))

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=SwarmRegistryOutput)
    def get_swarm_registry() -> ToolResult[SwarmRegistryOutput]:
        """List registered swarm configurations."""
        swarms = agent.swarm_registry.list_swarms_with_schemas() if agent.swarm_registry else []
        return ok(SwarmRegistryOutput(count=len(swarms), swarms=swarms))

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=GraphRegistryOutput)
    def get_graph_registry() -> ToolResult[GraphRegistryOutput]:
        """List registered graph configurations."""
        graphs = agent.graph_registry.list_graphs_with_schemas() if agent.graph_registry else []
        return ok(GraphRegistryOutput(count=len(graphs), graphs=graphs))

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=AgentRegistryOutput)
    def get_agent_registry() -> ToolResult[AgentRegistryOutput]:
        """List registered agent configurations."""
        agents = agent.agent_registry.list_agents() if agent.agent_registry else []
        return ok(AgentRegistryOutput(count=len(agents), agents=agents))

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def health_check() -> ToolResult[HealthOutput]:
        """Return basic health status for the SuperAgent."""
        return ok(HealthOutput.model_validate(agent.health_check()))

    @mcp.tool()
    @deterministic(input_model=WorkflowStatusInput, output_model=WorkflowStatusOutput)
    def get_workflow_status(workflow_id: str) -> ToolResult[WorkflowStatusOutput]:
        """Get a tracked workflow; absence is a normal domain result."""
        state = (agent.workflows or {}).get(workflow_id)
        if state is None:
            return ok(WorkflowStatusOutput(found=False, workflow_id=workflow_id))
        if hasattr(state, "to_dict"):
            value = state.to_dict()
        elif isinstance(state, dict):
            value = state
        else:
            value = {"status": getattr(state, "status", "unknown")}
        return ok(WorkflowStatusOutput(found=True, workflow_id=workflow_id, state=value))

    @mcp.tool()
    @operational(input_model=CancelWorkflowInput, output_model=CancelWorkflowOutput)
    def cancel_workflow(workflow_id: str) -> ToolResult[CancelWorkflowOutput]:
        """Cancel a tracked workflow; absence is a normal domain result."""
        state = (agent.workflows or {}).get(workflow_id)
        if state is None:
            return ok(CancelWorkflowOutput(success=False, workflow_id=workflow_id))
        if hasattr(state, "cancel"):
            state.cancel()
        return ok(CancelWorkflowOutput(success=True, workflow_id=workflow_id))

    @mcp.tool()
    @operational(input_model=InvokeSwarmInput, output_model=ExecutionOutput)
    async def invoke_swarm(swarm_id: str, task: str, context: dict[str, Any] | None = None) -> ToolResult[ExecutionOutput]:
        """Run registered personas through bounded LangGraph coordination."""
        from ..runtime.coordination import execute_registered
        config = agent.swarm_registry.get(swarm_id)
        if not config:
            return ok(ExecutionOutput(result={"success": False, "error": "not_found"}))
        return ok(ExecutionOutput(
            result=await execute_registered(config, task, context or {}),
        ))

    @mcp.tool()
    @operational(input_model=InvokeGraphInput, output_model=ExecutionOutput)
    async def invoke_graph(graph_id: str, task: str, context: dict[str, Any] | None = None) -> ToolResult[ExecutionOutput]:
        """Enroll a registered graph as a durable Workflow-managed run."""
        return ok(ExecutionOutput(
            result=await _launch_registered_graph(
                agent, graph_id, task, context or {}, launcher="invoke_graph",
            )
        ))

    @mcp.tool()
    @operational(input_model=ReasonInput, output_model=ExecutionOutput)
    async def reason(task: str, context: dict[str, Any] | None = None, agent_id: str | None = None) -> ToolResult[ExecutionOutput]:
        """Route a task to chat or an explicitly requested graph or swarm."""
        ctx = context or {}
        hints = ctx.pop("hints", None) or {}
        if agent_id:
            hints = {}
        result = await _reason(agent, task, ctx, hints, agent_id)
        return ok(ExecutionOutput(result=result))


async def _launch_registered_graph(
    agent: "SuperAgent", graph_id: str, task: str, context: dict[str, Any], *,
    launcher: str, requested_run_key: str | None = None,
) -> dict[str, Any]:
    """Validate and enroll one registry-selected graph without fallback."""
    from ..registry.launch_validator import skills_roots, validate_launch_context
    from ..runtime.managed_launch import launch_managed_graph, new_run_key

    config = agent.graph_registry.get(graph_id)
    if not config:
        return {"success": False, "status": "not_found", "error": "not_found"}
    ctx = dict(context)
    if isinstance(ctx.get("vuln_class"), str):
        ctx["vuln_class"] = ctx["vuln_class"].lower()
    raw = config.model_dump(by_alias=True) if hasattr(config, "model_dump") else config
    errors = validate_launch_context(raw, ctx, skills_dirs=skills_roots())
    if errors:
        return {
            "success": False, "status": "failed",
            "error": f"Launch validation failed: {errors[0]}",
            "validation_errors": errors,
        }
    run_key = new_run_key(
        graph_id, requested=requested_run_key or ctx.get("run_id"),
    )
    result = await launch_managed_graph(
        config, task, ctx, run_key=run_key, origin_kind="registered",
        invocation_state={"launcher": launcher},
    )
    return {"success": True, **result.model_dump(mode="json")}


async def _reason(agent: "SuperAgent", task: str, context: dict[str, Any], hints: dict[str, Any], agent_id: str | None) -> dict[str, Any]:
    """Run chat or explicitly requested bounded coordination."""
    if hints.get("swarm_id"):
        from ..runtime.coordination import execute_registered
        config = agent.swarm_registry.get(hints["swarm_id"])
        if config:
            result = await execute_registered(config, task, context)
            return {
                "workflow_type": "swarm", "workflow_id": result["run_id"],
                **result,
            }
    if "graph_id" in hints:
        graph_id = hints.get("graph_id")
        if not isinstance(graph_id, str) or not graph_id:
            return {
                "workflow_type": "graph", "workflow_id": "",
                "status": "not_found", "error": "not_found",
            }
        result = await _launch_registered_graph(
            agent, graph_id, task, context, launcher="reason",
        )
        return {
            "workflow_type": "graph",
            "workflow_id": str(result.get("run_id", "")),
            **result,
        }
    from ..runtime.chat import get_chat_agent
    chat = get_chat_agent()
    result = await chat.invoke(
        context.get("thread_id", "default"), task, agent_id=agent_id,
    )
    return {"workflow_type": "chat_agent", "status": result.status, "output": result.output}


def _resolve_available_tools() -> list[str]:
    """Resolve available tool names from the aggregator service registry."""
    try:
        from factory.mcp_utils.interface import get_service
        aggregate = getattr(get_service("tool_invoker"), "__self__", None)
        return aggregate.get_all_tool_names() if aggregate is not None else []
    except Exception:
        return []
