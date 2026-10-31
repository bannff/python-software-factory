"""First-class ``memory_scope`` propagation across Agent constructors (M6.5 s3).

Covers: the ``RuntimeInvocation`` contract default/validation; parent-scope
inheritance through LangGraph child nodes; context-scope derivation in the
coordination graph builder; the chat facade seam; and the hybrid-recall
consumer sending the exact owner-partitioned ``user_id`` to ``memory_retrieve``.
"""
from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest
pytest.importorskip("langchain")
pytest.importorskip("langgraph")
pytest.importorskip("langchain_community")

from factory.agent.runtime import coordination
from factory.agent.runtime.adapters.langchain_hybrid_recall import HybridRecallMCP
from factory.agent.runtime.adapters.langgraph_runtime import LangGraphRuntime
from factory.agent.runtime.runtime_contracts import (
    GraphEdge, GraphNode, GraphRequest, RuntimeInvocation, RuntimeResult,
)


def _base(**changes) -> RuntimeInvocation:
    values = {
        "invocation_id": "invoke", "agent_id": "developer", "prompt": "task",
        "capability_scope_digest": "scope",
    }
    values.update(changes)
    return RuntimeInvocation(**values)


def test_default_scope_is_backward_compatible() -> None:
    assert _base().memory_scope == "default"


@pytest.mark.parametrize("bad", ["", " default", "x" * 129, "line\nbreak"])
def test_contract_rejects_unbounded_or_empty_scope(bad: str) -> None:
    with pytest.raises(ValueError, match="memory_scope"):
        _base(memory_scope=bad)


@pytest.mark.asyncio
async def test_graph_child_inherits_parent_scope() -> None:
    class Agents:
        seen: list = []

        async def invoke(self, request):
            self.seen.append(request)
            return RuntimeResult(request.invocation_id, "done", "completed")

        async def close(self):
            return None

    agents = Agents()
    graph = LangGraphRuntime(agents)
    request = GraphRequest(
        invocation=_base(
            invocation_id="run-1", agent_id="graph", memory_scope="crew-alpha",
            thread_id="t", tenant_id="tenant", owner_id="owner",
        ),
        nodes=(GraphNode("worker", "worker"),), edges=(),
    )
    await graph.invoke_graph(request)
    assert agents.seen[0].memory_scope == "crew-alpha"
    await graph.close()


def test_coordination_derives_context_scope() -> None:
    config = {"id": "coord", "nodes": [{"id": "n1", "type": "agent"}], "edges": []}
    request = coordination.graph_request(
        config, "task", {"memory_scope": "crew-beta"}, "digest",
    )
    assert request.invocation.memory_scope == "crew-beta"


def test_coordination_defaults_scope_when_absent() -> None:
    config = {"id": "coord", "nodes": [{"id": "n1", "type": "agent"}], "edges": []}
    request = coordination.graph_request(config, "task", {}, "digest")
    assert request.invocation.memory_scope == "default"


def test_chat_facade_threads_configured_scope() -> None:
    from factory.agent.runtime.adapters.langchain_chat import LangChainChatAgent

    runtime = SimpleNamespace(capability_scope_digest="digest")
    agent = LangChainChatAgent(runtime, memory_scope="crew-gamma")
    request = agent._request("thread", "hi", "developer")  # noqa: SLF001
    assert request.memory_scope == "crew-gamma"


@pytest.mark.asyncio
async def test_hybrid_recall_sends_exact_partition_key() -> None:
    captured: dict[str, str] = {}

    class MCP(HybridRecallMCP):
        async def _call(self, request, brick, tool, arguments):
            if brick == "memory":
                captured["user_id"] = arguments["user_id"]
                return {"memories": []}
            return {"results": []} if brick == "kb" else {}

    request = _base(memory_scope="crew-delta", tenant_id="tenant", owner_id="owner-1")
    await MCP().recall(request)
    expected = hashlib.sha256(b"owner-1").hexdigest() + ".crew-delta"
    assert captured["user_id"] == expected


@pytest.mark.asyncio
async def test_hybrid_recall_fails_closed_on_invalid_scope() -> None:
    """An invalid scope must skip memory entirely, never fall back to raw owner."""
    class MCP(HybridRecallMCP):
        async def _call(self, request, brick, tool, arguments):
            assert brick != "memory", "memory must not be queried under bad scope"
            return {"results": []} if brick == "kb" else {}

    # Bypass the contract guard to prove the derivation itself fails closed.
    request = _base(tenant_id="tenant", owner_id="owner-1")
    object.__setattr__(request, "memory_scope", "BAD.SCOPE")
    result = await MCP().recall(request)
    assert result["memories"] == []


@pytest.mark.asyncio
async def test_temporary_mode_reads_no_memory_but_still_reads_kb() -> None:
    """Row 3 (feature-map), owner ruling 2026-09-16 21:20: "Temporary:
    read nothing, write nothing" — scoped to memory specifically. KB
    recall in the SAME hybrid call must be unaffected."""
    calls: list[str] = []

    class MCP(HybridRecallMCP):
        async def _call(self, request, brick, tool, arguments):
            calls.append(brick)
            if brick == "memory":
                return {"memories": [{"id": "should-never-appear", "content": "x"}]}
            return {"results": []} if brick == "kb" else {}

    request = _base(tenant_id="tenant", owner_id="owner-1", memory_mode="temporary")
    result = await MCP().recall(request)
    assert result["memories"] == []
    assert "memory" not in calls
    assert "kb" in calls


@pytest.mark.asyncio
async def test_incognito_mode_still_reads_memory() -> None:
    """The ruling's read/write split is real: Incognito reads memory
    (only writes are blocked), unlike Temporary which blocks both."""
    class MCP(HybridRecallMCP):
        async def _call(self, request, brick, tool, arguments):
            if brick == "memory":
                return {"memories": [{"id": "m1", "content": "still visible"}]}
            return {"results": []} if brick == "kb" else {}

    request = _base(tenant_id="tenant", owner_id="owner-1", memory_mode="incognito")
    result = await MCP().recall(request)
    assert len(result["memories"]) == 1
