"""Bounded provider-neutral execution for registered persona spawn tools."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from factory.mcp_utils.interface import CapabilityScope, get_capability_scope

from .adapters.capability_policy import delegation_allowed
from .runtime_contracts import GraphEdge, GraphNode, GraphRequest, RuntimeInvocation

LOG = logging.getLogger(__name__)

_MAX_AGENTS = 32


class SpawnCoordinator:
    """Execute one attempt locally; Workflow remains the durable owner."""

    def __init__(
        self, registry: Any,
        runtime_pair_factory: Callable[[CapabilityScope], tuple[Any, Any]] | None = None,
        *, timeout_seconds: float = 300.0,
    ) -> None:
        self._registry = registry
        self._factory = runtime_pair_factory
        self._timeout = timeout_seconds

    async def subagent(
        self, agent_id: str, task: str, context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        parent = self._parent_scope("subagent")
        if isinstance(parent, dict):
            return parent
        invalid = self._validate_agents([agent_id], "subagent", minimum=1)
        if invalid:
            return invalid
        agents, graph = self._pair(parent)
        invocation = self._invocation(agent_id, task, context, agents)
        try:
            async with asyncio.timeout(self._timeout):
                result = await agents.invoke(invocation)
            return self._result("subagent", result)
        except TimeoutError:
            return self._failure("subagent", "timeout", "execution_timeout")
        except Exception as exc:
            LOG.exception("subagent spawn failed")
            return self._failure("subagent", "failed", f"execution_failed: {exc}")
        finally:
            await graph.close()

    async def swarm(
        self, agent_ids: list[str], task: str, context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        parent = self._parent_scope("swarm")
        if isinstance(parent, dict):
            return parent
        invalid = self._validate_agents(agent_ids, "swarm", minimum=2)
        if invalid:
            return invalid
        edges = [GraphEdge(agent_ids[index], agent_ids[index + 1])
                 for index in range(len(agent_ids) - 1)]
        return await self._graph("swarm", agent_ids, edges, task, context, parent)

    async def graph(
        self, agent_ids: list[str], edges: list[dict[str, str]], task: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        parent = self._parent_scope("graph")
        if isinstance(parent, dict):
            return parent
        invalid = self._validate_agents(agent_ids, "graph", minimum=1)
        if invalid:
            return invalid
        parsed = [GraphEdge(str(edge.get("from", "")), str(edge.get("to", "")))
                  for edge in edges]
        edge_error = _validate_edges(agent_ids, parsed)
        if edge_error:
            return self._failure("graph", "rejected", edge_error)
        return await self._graph("graph", agent_ids, parsed, task, context, parent)

    async def _graph(
        self, kind: str, agent_ids: list[str], edges: list[GraphEdge], task: str,
        context: dict[str, Any] | None, parent_scope: CapabilityScope,
    ) -> dict[str, Any]:
        agents, graph = self._pair(parent_scope)
        invocation = self._invocation(kind, task, context, agents)
        request = GraphRequest(
            invocation=invocation,
            nodes=tuple(GraphNode(agent_id, agent_id) for agent_id in agent_ids),
            edges=tuple(edges), max_steps=min(2 * len(agent_ids), 64),
            timeout_seconds=self._timeout,
        )
        try:
            result = await graph.invoke_graph(request)
            return self._result(kind, result)
        except Exception as exc:
            LOG.exception("%s graph execution failed", kind)
            return self._failure(kind, "failed", f"execution_failed: {exc}")
        finally:
            await graph.close()

    def _pair(self, parent_scope: CapabilityScope) -> tuple[Any, Any]:
        if self._factory is None:
            from .adapters import create_runtime_pair
            return create_runtime_pair(parent_scope)
        return self._factory(parent_scope)

    def _parent_scope(self, kind: str) -> CapabilityScope | dict[str, Any]:
        scope = get_capability_scope()
        if scope is None:
            return self._failure(kind, "rejected", "scope_unavailable")
        if not delegation_allowed(scope):
            return self._failure(kind, "rejected", "delegation_depth_exceeded")
        return scope

    def _validate_agents(
        self, agent_ids: list[str], kind: str, *, minimum: int,
    ) -> dict[str, Any] | None:
        if len(agent_ids) < minimum:
            return self._failure(kind, "rejected", "insufficient_agents")
        if len(agent_ids) > _MAX_AGENTS:
            return self._failure(kind, "rejected", "too_many_agents")
        if len(set(agent_ids)) != len(agent_ids):
            return self._failure(kind, "rejected", "duplicate_agent_id")
        unknown = sorted(agent_id for agent_id in agent_ids if not self._registry.get(agent_id))
        if unknown:
            result = self._failure(kind, "rejected", "unknown_agent_id")
            result["unknown_agent_ids"] = unknown
            return result
        return None

    def _invocation(self, agent_id: str, task: str, context: dict[str, Any] | None, agents: Any) -> RuntimeInvocation:
        ctx = context or {}
        invocation_id = str(ctx.get("run_id") or ctx.get("invocation_id") or uuid4().hex)
        return RuntimeInvocation(
            invocation_id=invocation_id, agent_id=agent_id, prompt=task,
            capability_scope_digest=agents.capability_scope_digest,
            model_id=str(ctx.get("model_id") or ""),
            memory_scope=str(ctx.get("memory_scope") or "default"),
            thread_id=str(ctx.get("thread_id")) if ctx.get("thread_id") else None,
            metadata={key: str(value) for key, value in ctx.items()
                      if isinstance(value, (str, int, float, bool))},
        )

    @staticmethod
    def _result(kind: str, result: Any) -> dict[str, Any]:
        order = list(result.metadata.get("execution_order", ()))
        completed = result.status == "completed"
        return {"success": completed, "kind": kind,
                "status": "completed" if completed else "failed",
                "invocation_id": result.invocation_id,
                "output": result.output, "execution_order": order,
                "error_code": None if completed else "execution_failed"}

    @staticmethod
    def _failure(kind: str, status: str, code: str) -> dict[str, Any]:
        return {"success": False, "kind": kind, "status": status,
                "invocation_id": "", "output": "", "execution_order": [],
                "error_code": code}


def _validate_edges(agent_ids: list[str], edges: list[GraphEdge]) -> str | None:
    known = set(agent_ids)
    if any(not edge.source or not edge.target for edge in edges):
        return "invalid_edge"
    if any(edge.source not in known or edge.target not in known for edge in edges):
        return "unknown_edge_agent"
    if any(edge.source == edge.target for edge in edges):
        return "self_edge"
    if len({(edge.source, edge.target) for edge in edges}) != len(edges):
        return "duplicate_edge"
    incoming = {agent_id: 0 for agent_id in agent_ids}
    outgoing = {agent_id: [] for agent_id in agent_ids}
    for edge in edges:
        incoming[edge.target] += 1
        outgoing[edge.source].append(edge.target)
    pending = [agent_id for agent_id, count in incoming.items() if count == 0]
    visited = 0
    while pending:
        source = pending.pop()
        visited += 1
        for target in outgoing[source]:
            incoming[target] -= 1
            if incoming[target] == 0:
                pending.append(target)
    return None if visited == len(agent_ids) else "cyclic_edges"


__all__ = ["SpawnCoordinator"]
