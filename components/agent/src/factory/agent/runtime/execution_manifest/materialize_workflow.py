"""Materialize a registered WorkflowConfig as an ordinary typed GraphConfig."""
from __future__ import annotations

from typing import Any

from factory.agent.runtime.graph_contracts import AgentNodeRef, EdgeConfig, GraphConfig

from .preparation_support import partition_tools, render_text


def materialize_workflow_config(
    config: Any, context: dict[str, Any], *, model_override: str | None = None,
) -> GraphConfig:
    """Freeze factory tasks into graph data, optionally overriding every model."""
    from factory.agent.registry.factories import get_factory

    tasks = get_factory(config.factory)(context)
    task_ids = {str(task.get("task_id", "")) for task in tasks}
    if "" in task_ids or len(task_ids) != len(tasks):
        raise ValueError("workflow task ids must be non-empty and unique")
    nodes = []
    edges = []
    targets: set[str] = set()
    for task in tasks:
        task_id = str(task["task_id"])
        model = model_override or task.get("model_settings", {}).get("model_id")
        if not isinstance(model, str) or not model:
            raise ValueError(f"workflow task {task_id!r} has no model")
        local_tools, mcp_tools = partition_tools(task.get("tools", []))
        if config.tool_allowlist is not None:
            mcp_tools = [name for name in mcp_tools if name in config.tool_allowlist]
        payload: dict[str, Any] = {
            "id": task_id, "type": "agent",
            "description": render_text(str(task.get("description", "")), context),
            "system_prompt": render_text(str(task.get("system_prompt", "")), context),
            "model": model, "tools": local_tools,
            "skills": list(task.get("skills", [])), "context": {},
        }
        if mcp_tools:
            payload["mcp_tool_allowlist"] = mcp_tools
        nodes.append(AgentNodeRef.model_validate(payload))
        dependencies = list(task.get("dependencies", []))
        if len(dependencies) != len(set(dependencies)):
            raise ValueError(f"duplicate workflow dependency for {task_id!r}")
        for dependency in dependencies:
            if dependency not in task_ids:
                raise ValueError(f"unknown workflow dependency: {dependency!r}")
            edges.append(EdgeConfig(source=dependency, target=task_id))
            targets.add(task_id)
    return GraphConfig(
        id=config.id, name=config.name, description=config.description,
        nodes=nodes, edges=edges,
        entry_points=[node.id for node in nodes if node.id not in targets],
        execution_timeout=config.execution_timeout,
        node_timeout=config.node_timeout,
        required_bricks=list(config.required_bricks),
        context_vars=list(config.context_vars),
        tool_allowlist=config.tool_allowlist,
        resumable=True,
    )


__all__ = ["materialize_workflow_config"]
