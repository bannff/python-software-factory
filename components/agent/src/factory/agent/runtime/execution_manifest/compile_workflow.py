"""Compile WorkflowConfig factories into ordinary Agent DAGs."""
from __future__ import annotations

from typing import Any

from factory.agent.runtime.graph_contracts import AgentNodeRef

from .compile_agents import compile_agent
from .compiled import CompiledEdge, CompiledGraph
from .preparation_support import partition_tools, render_text


def compile_workflow(config: Any, context: dict[str, Any],
                     prefix: str = "") -> CompiledGraph:
    from factory.agent.registry.factories import get_factory

    tasks = get_factory(config.factory)(context)
    nodes = []
    edges: list[CompiledEdge] = []
    ids: set[str] = set()
    for task in tasks:
        task_id = str(task.get("task_id", ""))
        if not task_id or task_id in ids:
            raise ValueError("workflow task ids must be non-empty and unique")
        ids.add(task_id)
        model_id = task.get("model_settings", {}).get("model_id")
        if task.get("model_provider") != "bedrock" or not model_id:
            raise ValueError(f"unsupported workflow model descriptor for {task_id!r}")
        local, task_mcp = partition_tools(task.get("tools", []))
        if config.tool_allowlist is not None:
            task_mcp = [name for name in task_mcp if name in config.tool_allowlist]
        payload = {
            "id": f"{prefix}{task_id}", "type": "agent",
            "description": render_text(str(task.get("description", "")), context),
            "system_prompt": render_text(str(task.get("system_prompt", "")), context),
            "model": model_id, "tools": local, "skills": task.get("skills", []),
            "context": {},
        }
        if task_mcp:
            payload["mcp_tool_allowlist"] = task_mcp
        node = AgentNodeRef.model_validate(payload)
        nodes.append(compile_agent(node, context, config.tool_allowlist))
    for task in tasks:
        target = f"{prefix}{task['task_id']}"
        dependencies = task.get("dependencies", [])
        if len(dependencies) != len(set(dependencies)):
            raise ValueError(f"duplicate workflow dependency for {target!r}")
        for dependency in dependencies:
            if dependency not in ids:
                raise ValueError(f"unknown workflow dependency: {dependency!r}")
            edges.append(CompiledEdge(f"{prefix}{dependency}", target))
    targets = {edge.target for edge in edges}
    entries = tuple(node.id for node in nodes if node.id not in targets)
    return CompiledGraph(
        graph_id=config.id, name=config.name, description=config.description,
        nodes=tuple(nodes), edges=tuple(edges), entries=entries,
        max_node_executions=None, max_cycles=None,
        execution_timeout=config.execution_timeout, node_timeout=config.node_timeout,
    )


__all__ = ["compile_workflow"]
