"""Provider-neutral bounded coordination for registered personas."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from .runtime_contracts import GraphEdge, GraphNode, GraphRequest, RuntimeInvocation


def _value(item: Any, name: str, default: Any = None) -> Any:
    return item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)


def graph_request(
    config: Any, task: str, context: dict[str, Any], scope_digest: str,
) -> GraphRequest:
    """Translate a registered graph into the bounded neutral contract."""
    raw_nodes = _value(config, "nodes", ()) or ()
    unsupported = [node for node in raw_nodes if _value(node, "type") != "agent"]
    if unsupported:
        raise ValueError("LangGraph execution supports registered persona nodes only")
    nodes = tuple(
        GraphNode(_value(node, "id"), _value(node, "agent_id") or _value(node, "id"))
        for node in raw_nodes
    )
    edges = tuple(
        GraphEdge(_value(edge, "source"), _value(edge, "target"))
        for edge in (_value(config, "edges", ()) or ())
    )
    return GraphRequest(
        invocation=_invocation(config, task, context, scope_digest),
        nodes=nodes,
        edges=edges,
        max_steps=_value(config, "max_node_executions", None) or max(2 * len(nodes), 1),
        timeout_seconds=float(_value(config, "execution_timeout", 300.0)),
    )


def swarm_request(
    config: Any, task: str, context: dict[str, Any], scope_digest: str,
) -> GraphRequest:
    """Translate ordered registered swarm personas into a bounded pipeline."""
    agents = _value(config, "agents", ()) or ()
    nodes = tuple(GraphNode(_value(agent, "id"), _value(agent, "id")) for agent in agents)
    edges = tuple(
        GraphEdge(nodes[index].node_id, nodes[index + 1].node_id)
        for index in range(len(nodes) - 1)
    )
    return GraphRequest(
        invocation=_invocation(config, task, context, scope_digest),
        nodes=nodes, edges=edges,
        max_steps=min(int(_value(config, "max_iterations", 20)), 64),
        timeout_seconds=float(_value(config, "execution_timeout", 300.0)),
    )


def _invocation(
    config: Any, task: str, context: dict[str, Any], scope_digest: str,
) -> RuntimeInvocation:
    run_id = str(context.get("run_id") or context.get("workflow_run_id") or uuid4().hex)
    return RuntimeInvocation(
        invocation_id=run_id,
        agent_id=str(_value(config, "id", "coordinator")),
        prompt=task,
        capability_scope_digest=scope_digest,
        model_id=str(context.get("model_id") or _value(config, "model", "")),
        memory_scope=str(context.get("memory_scope") or "default"),
        thread_id=str(context.get("thread_id") or "") or None,
        metadata={
            key: str(value) for key, value in context.items()
            if isinstance(value, (str, int, float, bool))
        },
    )


async def execute_registered(config: Any, task: str, context: dict[str, Any]) -> dict[str, Any]:
    """Execute one graph/swarm registration through one scoped runtime pair."""
    from .adapters import create_runtime_pair

    agents, graph = create_runtime_pair()
    try:
        kind = _value(config, "kind", "graph")
        request = (
            swarm_request(config, task, context, agents.capability_scope_digest)
            if kind == "swarm" else
            graph_request(config, task, context, agents.capability_scope_digest)
        )
        result = await graph.invoke_graph(request)
        return {
            "status": result.status, "output": result.output,
            "run_id": result.invocation_id, **dict(result.metadata),
        }
    finally:
        await graph.close()


__all__ = ["execute_registered", "graph_request", "swarm_request"]
