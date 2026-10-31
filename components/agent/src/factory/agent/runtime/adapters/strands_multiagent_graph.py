"""Bounded DAG execution over the REAL ``strands.multiagent.Graph`` (#107).

A ``GraphRequest`` (persona nodes + edges + declared entry) compiles onto
``strands.multiagent.Graph``: node agents build through the SAME persona
path as chat (scoped capability tools via ``build_thread_agent_tools`` +
``AgentSkills`` plugins via ``persona_skills``), ``graph_bounds`` caps map
onto Graph's ``max_node_executions``/``execution_timeout``/``node_timeout``
(strands 1.56 has NO ``max_edge`` param — node-count overflow fails loudly
pre-build), and ``GraphResult`` status/execution_order/results map back
onto ``RuntimeResult``. Edge conditions: the closed registry only ever
declared ``all-predecessors-valid`` (the deleted ``graph_conditions``
semantics), which IS strands' readiness default for fail-fast DAGs; any
other kind raises naming it.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from ..graph_bounds import apply_execution_bounds, default_max_node_executions
from ..runtime_contracts import (
    GraphRequest, RuntimeLifecycleEvent, RuntimeResult,
)
from .strands_agent_factory import (
    bind_invocation, build_thread_agent_tools, reset_invocation,
)
from .strands_model import build_strands_model

_MAPPABLE_CONDITIONS = frozenset({None, "", "all-predecessors-valid"})


def _edge_condition(edge: Any) -> Any:
    """Map the declared condition kind; unmappable kinds fail loudly."""
    kind = getattr(edge, "condition", None)
    if kind in _MAPPABLE_CONDITIONS:
        return None  # all-predecessors readiness IS the strands DAG default
    raise ValueError(f"unmappable graph edge condition kind: {kind!r}")


def _node_event(raw: Any, emit: Any) -> RuntimeLifecycleEvent | None:
    """Translate one raw graph stream event (node stops only)."""
    if raw.get("type") != "multiagent_node_stop":
        return None
    node_result = raw["node_result"]
    status = node_result.status.value
    payload: dict[str, Any] = {
        "node_id": raw["node_id"], "output": str(node_result), "status": status,
    }
    structured = getattr(node_result.result, "structured_output", None)
    if structured is not None:
        payload["structured_output"] = structured
    return emit(
        "graph_node_completed" if status == "completed" else "graph_node_failed",
        payload,
    )


class StrandsMultiagentGraphExecutor:
    """Translate ``GraphRequest`` onto ``strands.multiagent.Graph``."""

    def __init__(
        self, agents: Any, *, model_builder: Any = None, max_nodes: int = 32,
    ) -> None:
        self._agents = agents
        self._model_builder = model_builder
        self._max_nodes = max_nodes

    async def invoke_graph(self, request: GraphRequest) -> RuntimeResult:
        graph = await self._compile(request)  # loud pre-build validation
        node_outputs: dict[str, str] = {}
        status = "completed"
        async for event in self._consume(request, graph):
            if event.kind == "graph_node_completed":
                node_outputs[str(event.payload["node_id"])] = str(event.payload["output"])
            elif event.kind == "graph_failed":
                status = str(event.payload["status"])
        text = "\n\n".join(
            node_outputs[node.node_id] for node in request.nodes
            if node.node_id in node_outputs
        )
        metadata: dict[str, Any] = {
            "execution_order": tuple(node_outputs), "node_outputs": dict(node_outputs),
        }
        return RuntimeResult(request.invocation.invocation_id, text, status, metadata)

    async def stream_graph(
        self, request: GraphRequest,
    ) -> AsyncIterator[RuntimeLifecycleEvent]:
        graph = await self._compile(request)
        async for event in self._consume(request, graph):
            yield event

    async def _consume(
        self, request: GraphRequest, graph: Any,
    ) -> AsyncIterator[RuntimeLifecycleEvent]:
        invocation_id = request.invocation.invocation_id
        token = bind_invocation(request.invocation)
        sequence = 0
        result: Any = None

        def _emit(kind: str, payload: dict[str, Any]) -> RuntimeLifecycleEvent:
            nonlocal sequence
            sequence += 1
            return RuntimeLifecycleEvent(invocation_id, sequence, kind, payload)

        try:
            yield _emit("graph_started", {"node_count": len(request.nodes)})
            async with asyncio.timeout(request.timeout_seconds):
                async for raw in graph.stream_async(request.invocation.prompt):
                    event = _node_event(raw, _emit)
                    if event is not None:
                        yield event
                    if raw.get("type") == "multiagent_result":
                        result = raw["result"]
            if result is not None and result.status.value == "failed":
                yield _emit("graph_failed", {"status": "failed"})
            else:
                yield _emit("graph_completed", {"status": "completed"})
        except TimeoutError:
            yield _emit("graph_failed", {"status": "timeout"})
        except asyncio.CancelledError:
            yield _emit("graph_failed", {"status": "cancelled"})
            raise
        except Exception:
            yield _emit("graph_failed", {"status": "failed"})
        finally:
            reset_invocation(token)

    async def _compile(self, request: GraphRequest) -> Any:
        from strands.multiagent import GraphBuilder

        nodes = request.nodes
        node_ids = [node.node_id for node in nodes]
        if not node_ids:
            raise ValueError("graph must declare at least one node")
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("graph node ids must be unique")
        if len(nodes) > self._max_nodes:
            raise ValueError(
                f"graph node count {len(nodes)} exceeds cap {self._max_nodes}",
            )
        known = set(node_ids)
        if any(edge.source not in known or edge.target not in known for edge in request.edges):
            raise ValueError("graph edge references an unknown node")
        builder = GraphBuilder()
        for node in nodes:
            builder.add_node(await self._node_agent(request, node), node.node_id)
        for edge in request.edges:
            builder.add_edge(edge.source, edge.target, _edge_condition(edge))
        entry = request.invocation.agent_id
        if entry in known:
            builder.set_entry_point(entry)
        apply_execution_bounds(builder, len(nodes))
        builder.set_max_node_executions(min(
            request.max_steps, default_max_node_executions(len(nodes)),
        ))
        builder.set_execution_timeout(request.timeout_seconds)
        return builder.build()

    async def _node_agent(self, request: GraphRequest, node: Any) -> Any:
        """Build the node Agent through the SAME persona path as chat."""
        from strands import Agent

        from ..personas import resolve_agent_config
        from ..steering_documents import apply_steering
        from .strands_skills import persona_skills

        persona = resolve_agent_config(node.agent_id)
        system_prompt, _digest = apply_steering(persona.system_prompt)
        model_builder = self._model_builder or build_strands_model
        model_id = request.invocation.model_id or getattr(self._agents, "_model_id", "")
        return Agent(
            agent_id=persona.id,
            name=f"{node.node_id}-{request.invocation.invocation_id}",
            system_prompt=system_prompt,
            model=model_builder(model_id, session_id=request.invocation.thread_id or ""),
            tools=await build_thread_agent_tools(self._agents.client, persona),
            callback_handler=None, plugins=persona_skills(persona),
        )


__all__ = ["StrandsMultiagentGraphExecutor"]
