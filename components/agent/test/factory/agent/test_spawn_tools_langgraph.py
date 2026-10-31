"""Behavior coverage for provider-neutral registered-persona spawning."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from factory.mcp_utils.interface import (
    bind_capability_scope, CapabilityScope, reset_capability_scope,
)

from factory.agent.runtime.runtime_contracts import RuntimeResult
from factory.agent.runtime.spawn import SpawnCoordinator


class _Registry:
    def __init__(self, *ids: str) -> None:
        self.ids = set(ids)

    def get(self, agent_id: str):
        return SimpleNamespace(id=agent_id) if agent_id in self.ids else None


class _Agents:
    capability_scope_digest = "a" * 64

    def __init__(self) -> None:
        self.requests = []

    async def invoke(self, request):
        self.requests.append(request)
        return RuntimeResult(request.invocation_id, f"ran:{request.agent_id}", "completed")


class _Graph:
    def __init__(self, agents: _Agents) -> None:
        self.agents = agents
        self.requests = []
        self.closed = False

    async def invoke_graph(self, request):
        self.requests.append(request)
        order = tuple(node.node_id for node in request.nodes)
        return RuntimeResult(
            request.invocation.invocation_id, "graph-output", "completed",
            {"execution_order": order},
        )

    async def close(self):
        self.closed = True


class _Pairs:
    def __init__(self) -> None:
        self.created = []
        self.parent_scopes = []

    def __call__(self, parent_scope):
        self.parent_scopes.append(parent_scope)
        agents = _Agents()
        graph = _Graph(agents)
        self.created.append((agents, graph))
        return agents, graph


@pytest.fixture(autouse=True)
def trusted_scope():
    scope = CapabilityScope.create(
        "spawn-test", {"agent_spawn_subagent", "sandbox_execute"},
    )
    token = bind_capability_scope(scope)
    try:
        yield scope
    finally:
        reset_capability_scope(token)


@pytest.mark.asyncio
async def test_spawn_subagent_runs_one_invocation_and_closes_runtime() -> None:
    pairs = _Pairs()
    result = await SpawnCoordinator(_Registry("writer"), pairs).subagent(
        "writer", "draft", {"thread_id": "t1"},
    )

    agents, graph = pairs.created[0]
    assert result["success"] is True and result["output"] == "ran:writer"
    assert agents.requests[0].agent_id == "writer"
    assert agents.requests[0].thread_id == "t1"
    assert graph.closed is True


@pytest.mark.asyncio
async def test_spawn_swarm_builds_ordered_bounded_graph() -> None:
    pairs = _Pairs()
    result = await SpawnCoordinator(_Registry("a", "b", "c"), pairs).swarm(
        ["a", "b", "c"], "solve",
    )

    request = pairs.created[0][1].requests[0]
    assert [(edge.source, edge.target) for edge in request.edges] == [
        ("a", "b"), ("b", "c"),
    ]
    assert request.max_steps == 6
    assert result["execution_order"] == ["a", "b", "c"]
    assert pairs.created[0][1].closed is True


@pytest.mark.asyncio
async def test_spawn_graph_preserves_valid_directed_edges() -> None:
    pairs = _Pairs()
    result = await SpawnCoordinator(_Registry("research", "review"), pairs).graph(
        ["research", "review"],
        [{"from": "research", "to": "review"}], "inspect",
    )

    request = pairs.created[0][1].requests[0]
    assert [(edge.source, edge.target) for edge in request.edges] == [
        ("research", "review"),
    ]
    assert result["success"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        (lambda service: service.subagent("missing", "task"), "unknown_agent_id"),
        (lambda service: service.swarm(["a"], "task"), "insufficient_agents"),
        (lambda service: service.swarm(["a", "missing"], "task"), "unknown_agent_id"),
        (lambda service: service.graph(
            ["a", "b"], [{"from": "a", "to": "outside"}], "task",
        ), "unknown_edge_agent"),
        (lambda service: service.graph(
            ["a", "b"], [{"from": "a", "to": "b"},
                           {"from": "b", "to": "a"}], "task",
        ), "cyclic_edges"),
    ],
)
async def test_invalid_personas_and_edges_are_safe_domain_results(operation, expected) -> None:
    pairs = _Pairs()
    result = await operation(SpawnCoordinator(_Registry("a", "b"), pairs))

    assert result["success"] is False
    assert result["status"] == "rejected"
    assert result["error_code"] == expected
    assert pairs.created == []
    assert "exception" not in result
