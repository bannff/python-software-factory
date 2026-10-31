"""MCP-layer canary for ``memory_history`` (row 47 — Replaced experiences,
informational only: no restore action by owner ruling)."""
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


def test_history_reports_supported_false_on_a_non_graph_adapter() -> None:
    runtime = MemoryRuntime(store=InMemoryStore())
    memory = runtime.store(user_id="u1", content="alpha")
    server = create_server(runtime)

    result = _call_tool(server, "memory_history", memory_id=memory.id)

    assert result.ok is True
    assert result.data.supported is False
    assert result.data.versions == []


def test_history_returns_the_full_chain_newest_first_on_the_graph_adapter() -> None:
    store = GraphMemoryStore(runtime=GraphRuntime(), backend="networkx")
    runtime = MemoryRuntime(store=store)
    original = runtime.store(user_id="u1", content="v1")
    replacement = runtime.store(user_id="u1", content="v2")
    assert store.supersede(original.id, replacement.id) is True
    server = create_server(runtime)

    result = _call_tool(server, "memory_history", memory_id=original.id)

    assert result.ok is True
    assert result.data.supported is True
    assert [v.id for v in result.data.versions] == [replacement.id, original.id]


def test_history_called_on_an_id_that_does_not_exist_returns_an_empty_supported_chain() -> None:
    store = GraphMemoryStore(runtime=GraphRuntime(), backend="networkx")
    runtime = MemoryRuntime(store=store)
    server = create_server(runtime)

    result = _call_tool(server, "memory_history", memory_id="nonexistent-id")

    assert result.ok is True
    assert result.data.supported is True
    assert result.data.versions == []
