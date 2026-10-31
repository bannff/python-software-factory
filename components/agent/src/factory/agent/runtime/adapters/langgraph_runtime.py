"""Bounded, attempt-local LangGraph implementation of GraphRuntimePort."""
from __future__ import annotations

import asyncio
import operator
from collections.abc import AsyncIterator
from typing import Annotated, Any, TypedDict

from ..runtime_contracts import (
    GraphRequest, RuntimeInvocation, RuntimeLifecycleEvent, RuntimeResult,
)
from .langchain_runtime import LangChainAgentRuntime


class _GraphState(TypedDict):
    prompt: str
    outputs: Annotated[list[tuple[str, str]], operator.add]
    structured_outputs: Annotated[list[tuple[str, dict[str, Any]]], operator.add]


class LangGraphRuntime:
    """Execute declared persona DAGs without durable lifecycle ownership."""

    def __init__(
        self, agents: LangChainAgentRuntime, *, max_nodes: int = 32,
        max_steps: int = 64, timeout_seconds: float = 300.0,
    ) -> None:
        self._agents = agents
        self._max_nodes = max_nodes
        self._max_steps = max_steps
        self._timeout = timeout_seconds
        self._active: dict[str, asyncio.Task[Any]] = {}

    @property
    def descriptor(self):
        """Use the concrete LangChain/LangGraph package identity."""
        return self._agents.descriptor

    async def invoke_graph(self, request: GraphRequest) -> RuntimeResult:
        outputs: dict[str, str] = {}
        structured_outputs: dict[str, dict[str, Any]] = {}
        status = "completed"
        async for event in self.stream_graph(request):
            if event.kind == "graph_node_completed":
                outputs[str(event.payload["node_id"])] = str(event.payload["output"])
                structured = event.payload.get("structured_output")
                if structured is not None:
                    structured_outputs[str(event.payload["node_id"])] = structured
            elif event.kind == "graph_failed":
                status = str(event.payload.get("status", "failed"))
        leaves = self._leaves(request)
        text = "\n\n".join(outputs[node] for node in leaves if node in outputs)
        metadata: dict[str, Any] = {"execution_order": tuple(outputs), "node_outputs": outputs}
        if structured_outputs:
            # M7.6 exit criterion #2 (feature-map): keyed by AGENT_ID, not
            # node_id -- ``loop_reconcile._outcome`` reads
            # ``structured_outputs[agent_id]``, and a manifest's node id
            # and agent id are not always the same string (though for the
            # single-node managed-loop path they are, by construction).
            by_agent = {
                next(node.agent_id for node in request.nodes if node.node_id == node_id): value
                for node_id, value in structured_outputs.items()
            }
            metadata["structured_outputs"] = by_agent
        return RuntimeResult(request.invocation.invocation_id, text, status, metadata)

    async def stream_graph(
        self, request: GraphRequest,
    ) -> AsyncIterator[RuntimeLifecycleEvent]:
        graph = self._compile(request)
        invocation_id = request.invocation.invocation_id
        sequence = 1
        yield RuntimeLifecycleEvent(invocation_id, sequence, "graph_started", {
            "node_count": len(request.nodes), "max_steps": self._step_limit(request),
        })
        task = asyncio.current_task()
        if task is not None:
            self._active[invocation_id] = task
        try:
            source = graph.astream(
                {"prompt": request.invocation.prompt, "outputs": [], "structured_outputs": []},
                config={"recursion_limit": self._step_limit(request)},
                stream_mode="updates",
            )
            async with asyncio.timeout(self._timeout_limit(request)):
                async for update in source:
                    for node_id, delta in update.items():
                        structured_by_node = dict(delta.get("structured_outputs", ()))
                        for output_node, output in delta.get("outputs", ()):
                            sequence += 1
                            resolved_node = output_node or node_id
                            payload: dict[str, Any] = {
                                "node_id": resolved_node, "output": output,
                            }
                            if resolved_node in structured_by_node:
                                payload["structured_output"] = structured_by_node[resolved_node]
                            yield RuntimeLifecycleEvent(
                                invocation_id, sequence, "graph_node_completed", payload,
                            )
            sequence += 1
            yield RuntimeLifecycleEvent(
                invocation_id, sequence, "graph_completed", {"status": "completed"},
            )
        except TimeoutError:
            sequence += 1
            yield RuntimeLifecycleEvent(
                invocation_id, sequence, "graph_failed", {"status": "timeout"},
            )
        except asyncio.CancelledError:
            sequence += 1
            yield RuntimeLifecycleEvent(
                invocation_id, sequence, "graph_failed", {"status": "cancelled"},
            )
        finally:
            self._active.pop(invocation_id, None)

    def _compile(self, request: GraphRequest) -> Any:
        node_ids = [node.node_id for node in request.nodes]
        if not node_ids or len(node_ids) > self._max_nodes:
            raise ValueError(f"graph node count must be between 1 and {self._max_nodes}")
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("graph node ids must be unique")
        known = set(node_ids)
        if any(edge.source not in known or edge.target not in known for edge in request.edges):
            raise ValueError("graph edge references an unknown node")
        predecessors = {
            node_id: tuple(edge.source for edge in request.edges if edge.target == node_id)
            for node_id in node_ids
        }
        roots = [node_id for node_id in node_ids if not predecessors[node_id]]
        if not roots:
            raise ValueError("graph must have at least one entry node")
        from langgraph.graph import END, START, StateGraph

        builder = StateGraph(_GraphState)
        for node in request.nodes:
            builder.add_node(node.node_id, self._node(request, node, predecessors[node.node_id]))
        for root in roots:
            builder.add_edge(START, root)
        for edge in request.edges:
            builder.add_edge(edge.source, edge.target)
        for leaf in self._leaves(request):
            builder.add_edge(leaf, END)
        return builder.compile()

    def _node(self, request: GraphRequest, node: Any, predecessors: tuple[str, ...]):
        async def execute(state: _GraphState) -> dict[str, list[Any]]:
            prior = {key: value for key, value in state["outputs"]}
            context = "\n\n".join(
                f"Output from {key}:\n{prior[key]}" for key in predecessors if key in prior
            )
            prompt = state["prompt"] if not context else f"{state['prompt']}\n\n{context}"
            parent = request.invocation
            result = await self._agents.invoke(RuntimeInvocation(
                invocation_id=f"{parent.invocation_id}:{node.node_id}",
                agent_id=node.agent_id,
                prompt=prompt,
                capability_scope_digest=parent.capability_scope_digest,
                model_id=parent.model_id,
                memory_scope=parent.memory_scope,
                output_schema=node.output_schema or "",
                thread_id=(parent.thread_id if parent.metadata.get("background_subagent") == "true"
                           else f"{parent.thread_id}:{node.node_id}" if parent.thread_id else None),
                tenant_id=parent.tenant_id, owner_id=parent.owner_id,
                metadata={**parent.metadata, "graph_node_id": node.node_id},
            ))
            if result.status != "completed":
                raise RuntimeError(f"graph node {node.node_id} ended with {result.status}")
            update: dict[str, list[Any]] = {"outputs": [(node.node_id, result.output)]}
            structured = result.metadata.get("structured_response")
            if structured is not None:
                update["structured_outputs"] = [(node.node_id, structured)]
            return update
        return execute

    def _leaves(self, request: GraphRequest) -> tuple[str, ...]:
        sources = {edge.source for edge in request.edges}
        return tuple(node.node_id for node in request.nodes if node.node_id not in sources)

    def _step_limit(self, request: GraphRequest) -> int:
        return min(request.max_steps, self._max_steps)

    def _timeout_limit(self, request: GraphRequest) -> float:
        return min(request.timeout_seconds, self._timeout)

    async def cancel(self, invocation_id: str) -> None:
        task = self._active.get(invocation_id)
        if task is not None and task is not asyncio.current_task():
            task.cancel()

    async def close(self) -> None:
        for invocation_id in tuple(self._active):
            await self.cancel(invocation_id)
        await self._agents.close()


__all__ = ["LangGraphRuntime"]
