"""Typed public-boundary regression tests for graph Storage MCP tools."""
from __future__ import annotations

import asyncio

import pytest
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from factory.mcp_utils.interface import ToolResult
from factory.storage.mcp.graph_tools import _edge, _node, register
from factory.storage.runtime.ports.graph import GraphQueryResult
from factory.storage.runtime.runtime import StorageRuntime, reset_runtime


class TestGraphTools:
    """Preserve graph behavior while asserting the typed result envelope."""

    @pytest.fixture(autouse=True)
    def reset(self) -> None:
        reset_runtime()

    @pytest.fixture
    def runtime(self) -> StorageRuntime:
        return StorageRuntime()

    @pytest.fixture
    def mcp(self, runtime: StorageRuntime) -> ToolCatalog:
        server = ToolCatalog("test-graph")
        register(server, lambda: runtime)
        return server

    def _call(self, mcp: ToolCatalog, name: str, **kwargs):
        result = asyncio.run(mcp.get_tool(name)).fn(**kwargs)
        assert isinstance(result, ToolResult)
        assert result.ok is True
        return result.data

    def test_all_tools_registered(self, mcp: ToolCatalog) -> None:
        expected = {
            "graph_add_node", "graph_get_node", "graph_update_node",
            "graph_delete_node", "graph_add_edge", "graph_get_edges",
            "graph_delete_edge", "graph_query",
        }
        for name in expected:
            assert asyncio.run(mcp.get_tool(name)) is not None, f"{name} not registered"

    def test_add_node_returns_typed_shape(self, mcp: ToolCatalog) -> None:
        result = self._call(mcp, "graph_add_node", labels=["Person"], properties={"name": "Alice"})
        assert result.id
        assert result.labels == ["Person"]
        assert result.properties["name"] == "Alice"

    def test_add_node_without_properties(self, mcp: ToolCatalog) -> None:
        result = self._call(mcp, "graph_add_node", labels=["Tag"])
        assert result.labels == ["Tag"]
        assert isinstance(result.properties, dict)

    def test_get_node_existing(self, mcp: ToolCatalog) -> None:
        added = self._call(mcp, "graph_add_node", labels=["X"], properties={"k": "v"})
        got = self._call(mcp, "graph_get_node", node_id=added.id)
        assert got.found is True
        assert got.id == added.id
        assert got.properties["k"] == "v"

    def test_get_node_missing_returns_success_data(self, mcp: ToolCatalog) -> None:
        result = self._call(mcp, "graph_get_node", node_id="no-such-id")
        assert result.found is False
        assert result.error == "not_found"
        assert result.node_id == "no-such-id"

    def test_update_node_merges_properties(self, mcp: ToolCatalog) -> None:
        added = self._call(mcp, "graph_add_node", labels=["P"], properties={"a": 1})
        updated = self._call(mcp, "graph_update_node", node_id=added.id, properties={"b": 2})
        assert updated.found is True
        assert updated.properties == {"a": 1, "b": 2}

    def test_update_node_missing_returns_success_data(self, mcp: ToolCatalog) -> None:
        result = self._call(mcp, "graph_update_node", node_id="ghost", properties={"x": 1})
        assert result.found is False
        assert result.error == "not_found"

    def test_delete_node_existing_and_missing(self, mcp: ToolCatalog) -> None:
        added = self._call(mcp, "graph_add_node", labels=["D"], properties={})
        deleted = self._call(mcp, "graph_delete_node", node_id=added.id)
        assert deleted.deleted is True
        assert deleted.node_id == added.id
        assert self._call(mcp, "graph_delete_node", node_id="nope").deleted is False

    def test_add_edge_returns_typed_shape(self, mcp: ToolCatalog) -> None:
        source = self._call(mcp, "graph_add_node", labels=["N"], properties={"id": "a"})
        target = self._call(mcp, "graph_add_node", labels=["N"], properties={"id": "b"})
        edge = self._call(mcp, "graph_add_edge", source_id=source.id, target_id=target.id, edge_type="LINKS", properties={"w": 1})
        assert edge.id
        assert edge.source_id == source.id
        assert edge.target_id == target.id
        assert edge.type == "LINKS"
        assert edge.properties["w"] == 1

    def test_get_edges_returns_list_and_empty_data(self, mcp: ToolCatalog) -> None:
        source = self._call(mcp, "graph_add_node", labels=["N"], properties={"id": "a"})
        target = self._call(mcp, "graph_add_node", labels=["N"], properties={"id": "b"})
        self._call(mcp, "graph_add_edge", source_id=source.id, target_id=target.id, edge_type="E")
        result = self._call(mcp, "graph_get_edges", node_id=source.id, direction="out")
        assert result.count == 1
        assert len(result.edges) == 1
        lone = self._call(mcp, "graph_add_node", labels=["N"], properties={"id": "lone"})
        empty = self._call(mcp, "graph_get_edges", node_id=lone.id)
        assert empty.count == 0
        assert empty.edges == []

    def test_delete_edge_existing_and_missing(self, mcp: ToolCatalog) -> None:
        source = self._call(mcp, "graph_add_node", labels=["N"], properties={})
        target = self._call(mcp, "graph_add_node", labels=["N"], properties={})
        edge = self._call(mcp, "graph_add_edge", source_id=source.id, target_id=target.id, edge_type="E")
        assert self._call(mcp, "graph_delete_edge", edge_id=edge.id).deleted is True
        assert self._call(mcp, "graph_delete_edge", edge_id="no-edge").deleted is False

    def test_query_returns_typed_nodes_edges_and_raw(self, mcp: ToolCatalog) -> None:
        self._call(mcp, "graph_add_node", labels=["Q"], properties={"v": 1})
        result = self._call(mcp, "graph_query", cypher="MATCH (n) RETURN n")
        assert result.nodes
        assert result.edges == []
        assert isinstance(result.raw, list)

    def test_query_preserves_ordered_raw_rows(self, mcp: ToolCatalog, runtime: StorageRuntime) -> None:
        raw_rows = [
            {"tool_name": "cache_get", "brick": "cache", "workflow_run_id": "run-b"},
            {"tool_name": "agent_reason", "brick": "agent", "workflow_run_id": "run-a"},
        ]
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(runtime.get_graph_store(), "query", lambda cypher, params=None: GraphQueryResult(raw=raw_rows))
            result = self._call(mcp, "graph_query", cypher="MATCH (t:ToolInvocation) RETURN t ORDER BY t.created_at DESC")
        assert result.raw == raw_rows


class TestHelperFunctions:
    def test_node_to_dict(self) -> None:
        class FakeNode:
            id = "n1"
            labels = ["A", "B"]
            properties = {"key": "val"}

        assert _node(FakeNode()).model_dump() == {"id": "n1", "labels": ["A", "B"], "properties": {"key": "val"}}

    def test_edge_to_dict(self) -> None:
        class FakeEdge:
            id = "e1"
            source_id = "s"
            target_id = "t"
            type = "REL"
            properties = {"w": 5}

        assert _edge(FakeEdge()).model_dump() == {"id": "e1", "source_id": "s", "target_id": "t", "type": "REL", "properties": {"w": 5}}
