"""MCP-layer canary for ``memory_recall_inspect`` (row 45's recall
inspection, owner direction 2026-09-16)."""
from __future__ import annotations

import asyncio

from factory.graph.interface import GraphRuntime
from factory.memory.interface import create_server
from factory.memory.runtime.adapters.graph_store import GraphMemoryStore
from factory.memory.runtime.adapters.memory import InMemoryStore
from factory.memory.runtime.runtime import MemoryRuntime


def _call_tool(server, tool_name: str, **kwargs):
    tool = asyncio.run(server.get_tool(tool_name))
    if tool is None:
        raise ValueError(f"Tool '{tool_name}' not found.")
    return tool.fn(**kwargs)


class _FakeSemanticEmbedder:
    is_semantic = True

    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


def test_recall_inspect_reports_supported_false_on_a_non_graph_adapter() -> None:
    runtime = MemoryRuntime(store=InMemoryStore())
    memory = runtime.store(user_id="u1", content="alpha")
    server = create_server(runtime)

    result = _call_tool(server, "memory_recall_inspect", memory_id=memory.id)

    assert result.ok is True
    assert result.data.supported is False
    assert result.data.similar == []


def test_recall_inspect_reports_the_real_similarity_score_on_the_graph_adapter() -> None:
    store = GraphMemoryStore(runtime=GraphRuntime(), embedder=_FakeSemanticEmbedder(), backend="networkx")
    runtime = MemoryRuntime(store=store)
    first = runtime.store(user_id="u1", content="alpha")
    second = runtime.store(user_id="u1", content="alpha again")
    server = create_server(runtime)

    result = _call_tool(server, "memory_recall_inspect", memory_id=second.id)

    assert result.ok is True
    assert result.data.supported is True
    assert result.data.owner_id == "u1"
    assert result.data.followed is not None and result.data.followed.id == first.id
    assert len(result.data.similar) == 1
    assert result.data.similar[0].memory.id == first.id
    assert result.data.similar[0].score == 1.0
