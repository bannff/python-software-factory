"""MCP-layer canary for ``memory_retrieve(tags=...)``.

bd:python-factory-lin6p (epic python-factory-hadbi). Ensures the
``tags`` param threads cleanly from the FastMCP tool surface through the
``MemoryRuntime`` and into ``MemoryQuery`` without dropping. Also confirms
the default behaviour (no ``tags`` arg) matches today's contract.
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from factory.memory.interface import create_server
from factory.memory.runtime.models import MemoryQuery


def _call_tool(server, tool_name: str, **kwargs):
    tool = asyncio.run(server.get_tool(tool_name))
    if tool is None:
        raise ValueError(f"Tool '{tool_name}' not found.")
    return tool.fn(**kwargs)


def _silent_invoker():
    return patch(
        "factory.mcp_utils.registry._services", {"tool_invoker": MagicMock()},
    )


class TestMemoryRetrieveTagsMCPThreading:
    def test_memory_query_accepts_tags_field(self) -> None:
        q = MemoryQuery(user_id="u", query="x", tags=["wine-pairing-learnings"])
        assert q.tags == ["wine-pairing-learnings"]

    def test_memory_query_tags_default_none(self) -> None:
        q = MemoryQuery(user_id="u", query="x")
        assert q.tags is None

    def test_memory_query_tags_empty_list_distinct_from_none(self) -> None:
        q = MemoryQuery(user_id="u", query="x", tags=[])
        assert q.tags == []
        assert q.tags is not None

    def test_mcp_tool_threads_tags_into_runtime(self) -> None:
        server = create_server()
        with _silent_invoker():
            _call_tool(
                server, "memory_store",
                user_id="u-mcp", content="security-1",
                metadata={"tags": ["security-learnings"]},
            )
            _call_tool(
                server, "memory_store",
                user_id="u-mcp", content="wine-1",
                metadata={"tags": ["wine-pairing-learnings"]},
            )
            results = _call_tool(
                server, "memory_retrieve",
                user_id="u-mcp", query="learnings",
                min_relevance=0.0,
                tags=["wine-pairing-learnings"],
            )
        assert all(
            "wine-pairing-learnings" in r.metadata.get("tags", [])
            for r in results.data.memories
        )
        assert all(r.content == "wine-1" for r in results.data.memories)

    def test_mcp_default_no_tags_arg_preserves_existing_behavior(self) -> None:
        server = create_server()
        with _silent_invoker():
            _call_tool(
                server, "memory_store",
                user_id="u-mcp-d", content="alpha",
                metadata={"tags": ["x"]},
            )
            _call_tool(
                server, "memory_store",
                user_id="u-mcp-d", content="beta",
                metadata={"tags": ["y"]},
            )
            without_tags = _call_tool(
                server, "memory_retrieve",
                user_id="u-mcp-d", query="alpha", min_relevance=0.0,
            )
            with_explicit_none = _call_tool(
                server, "memory_retrieve",
                user_id="u-mcp-d", query="alpha", min_relevance=0.0, tags=None,
            )
        assert {r.id for r in without_tags.data.memories} == {
            r.id for r in with_explicit_none.data.memories
        }

    def test_mcp_tool_tags_empty_returns_empty(self) -> None:
        server = create_server()
        with _silent_invoker():
            _call_tool(
                server, "memory_store",
                user_id="u-mcp-e", content="alpha",
                metadata={"tags": ["x"]},
            )
            results = _call_tool(
                server, "memory_retrieve",
                user_id="u-mcp-e", query="alpha",
                min_relevance=0.0, tags=[],
            )
        assert results.ok and results.data.memories == []
