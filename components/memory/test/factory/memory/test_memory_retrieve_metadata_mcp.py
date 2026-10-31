"""MCP-layer canary for ``memory_retrieve(metadata=...)``.

bd:python-factory-b2d2o (epic python-factory-hadbi). Pins:

* ``MemoryQuery.metadata`` accepts ``dict[str, str]`` and defaults to
  ``None``.
* The FastMCP tool surface threads ``metadata`` cleanly through to
  ``MemoryRuntime.retrieve``.
* The Cypher-injection guard fires at the MCP boundary too — unsafe
  keys raise ``ValidationError`` before any adapter is touched.
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

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


class TestMemoryRetrieveMetadataMCPThreading:
    def test_memory_query_accepts_metadata_field(self) -> None:
        q = MemoryQuery(user_id="u", query="x", metadata={"run_id": "r-1"})
        assert q.metadata == {"run_id": "r-1"}

    def test_memory_query_metadata_default_none(self) -> None:
        q = MemoryQuery(user_id="u", query="x")
        assert q.metadata is None

    def test_memory_query_metadata_empty_dict_distinct_from_none_at_field(
        self,
    ) -> None:
        """Field preserves the literal — runtime treats both as
        no-filter (asymmetric default), but the contract round-trips."""
        q = MemoryQuery(user_id="u", query="x", metadata={})
        assert q.metadata == {}
        assert q.metadata is not None

    def test_mcp_tool_threads_metadata_into_runtime(self) -> None:
        server = create_server()
        with _silent_invoker():
            _call_tool(
                server, "memory_store",
                user_id="u-mcp", content="run-1-event",
                metadata={"run_id": "r-1", "agent_id": "wine-1"},
            )
            _call_tool(
                server, "memory_store",
                user_id="u-mcp", content="run-2-event",
                metadata={"run_id": "r-2", "agent_id": "sec-1"},
            )
            results = _call_tool(
                server, "memory_retrieve",
                user_id="u-mcp", query="event",
                min_relevance=0.0,
                metadata={"run_id": "r-1"},
            )
        assert all(r.metadata.get("run_id") == "r-1" for r in results.data.memories)
        assert all(r.content == "run-1-event" for r in results.data.memories)

    def test_mcp_default_no_metadata_arg_preserves_existing_behavior(
        self,
    ) -> None:
        server = create_server()
        with _silent_invoker():
            _call_tool(
                server, "memory_store",
                user_id="u-mcp-d", content="alpha",
                metadata={"run_id": "r-1"},
            )
            _call_tool(
                server, "memory_store",
                user_id="u-mcp-d", content="beta",
                metadata={"run_id": "r-2"},
            )
            without_metadata = _call_tool(
                server, "memory_retrieve",
                user_id="u-mcp-d", query="alpha", min_relevance=0.0,
            )
            with_explicit_none = _call_tool(
                server, "memory_retrieve",
                user_id="u-mcp-d", query="alpha", min_relevance=0.0,
                metadata=None,
            )
        assert {r.id for r in without_metadata.data.memories} == {
            r.id for r in with_explicit_none.data.memories
        }

    def test_mcp_metadata_empty_dict_equals_no_filter(self) -> None:
        """Asymmetric default: {} is no-filter (NOT match-nothing)."""
        server = create_server()
        with _silent_invoker():
            _call_tool(
                server, "memory_store",
                user_id="u-mcp-e", content="alpha",
                metadata={"run_id": "r-1"},
            )
            none_results = _call_tool(
                server, "memory_retrieve",
                user_id="u-mcp-e", query="alpha",
                min_relevance=0.0, metadata=None,
            )
            empty_results = _call_tool(
                server, "memory_retrieve",
                user_id="u-mcp-e", query="alpha",
                min_relevance=0.0, metadata={},
            )
        assert {r.id for r in none_results.data.memories} == {
            r.id for r in empty_results.data.memories
        }

    def test_mcp_tool_threads_metadata_with_tags_compose(self) -> None:
        """Cross-filter at MCP boundary: tags ∧ metadata = intersection."""
        server = create_server()
        with _silent_invoker():
            _call_tool(
                server, "memory_store",
                user_id="u-mcp-c", content="m1",
                metadata={"tags": ["wine"], "run_id": "r-1"},
            )
            _call_tool(
                server, "memory_store",
                user_id="u-mcp-c", content="m2",
                metadata={"tags": ["wine"], "run_id": "r-2"},
            )
            results = _call_tool(
                server, "memory_retrieve",
                user_id="u-mcp-c", query="m",
                min_relevance=0.0,
                tags=["wine"], metadata={"run_id": "r-1"},
            )
        assert all(r.content == "m1" for r in results.data.memories)


class TestCypherInjectionGuardAtMCPBoundary:
    def test_unsafe_key_raises_validation_error_before_adapter(self) -> None:
        """The Pydantic field_validator on ``MemoryQuery.metadata``
        fires at construction — verifies the guard is reachable from
        any caller that builds a ``MemoryQuery``."""
        with pytest.raises(ValidationError):
            MemoryQuery(
                user_id="u", query="x",
                metadata={"run_id; MATCH (n) DETACH DELETE n; //": "r"},
            )

    def test_unsafe_key_at_runtime_raises_too(self) -> None:
        """``MemoryRuntime.retrieve`` builds a ``MemoryQuery``
        internally — the guard fires there as well, defense in depth."""
        from factory.memory.runtime.adapters.memory import InMemoryStore
        from factory.memory.runtime.runtime import MemoryRuntime
        rt = MemoryRuntime(store=InMemoryStore())
        with _silent_invoker(), pytest.raises(ValidationError):
            rt.retrieve(
                user_id="u", query="x",
                metadata={"x with space": "v"},
            )
