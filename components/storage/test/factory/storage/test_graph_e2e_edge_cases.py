"""E2E tests: graph edge cases and error conditions.

Part 3 of the graph E2E suite — exercises boundary conditions,
error handling, and unusual inputs for graph MCP tools.
See .agents/recipes/data-layer.md Step 9.
"""

from __future__ import annotations

import asyncio

import pytest
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from factory.storage.server import create_mcp_server
from factory.storage.runtime.runtime import StorageRuntime, reset_runtime


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_global_runtime():
    reset_runtime()
    yield
    reset_runtime()


@pytest.fixture
def runtime() -> StorageRuntime:
    return StorageRuntime()


@pytest.fixture
def mcp(runtime: StorageRuntime) -> ToolCatalog:
    return create_mcp_server(runtime)


def _call(mcp: ToolCatalog, name: str, **kwargs):
    tool = asyncio.run(mcp.get_tool(name))
    result = tool.fn(**kwargs)
    assert result.ok
    return result.data.model_dump()


# ── Edge Cases ──────────────────────────────────────────────────────


class TestGraphEdgeCases:
    """Edge cases and error conditions for graph tools."""

    def test_add_node_empty_labels(self, mcp: ToolCatalog) -> None:
        r = _call(mcp, "graph_add_node", labels=[], properties={"x": 1})
        assert r["labels"] == []

    def test_add_node_multiple_labels(self, mcp: ToolCatalog) -> None:
        r = _call(mcp, "graph_add_node",
                   labels=["Document", "Markdown", "Reviewed"], properties={})
        assert r["labels"] == ["Document", "Markdown", "Reviewed"]

    def test_add_node_empty_properties(self, mcp: ToolCatalog) -> None:
        r = _call(mcp, "graph_add_node", labels=["Empty"])
        assert r["properties"] == {}

    def test_add_node_unicode_properties(self, mcp: ToolCatalog) -> None:
        r = _call(mcp, "graph_add_node", labels=["Doc"],
                   properties={"title": "日本語テスト", "emoji": "🚀"})
        assert r["properties"]["title"] == "日本語テスト"

    def test_add_node_nested_properties(self, mcp: ToolCatalog) -> None:
        r = _call(mcp, "graph_add_node", labels=["Complex"],
                   properties={"meta": {"nested": True, "depth": 2}})
        assert r["properties"]["meta"]["nested"] is True

    def test_get_node_nonexistent(self, mcp: ToolCatalog) -> None:
        r = _call(mcp, "graph_get_node", node_id="does-not-exist")
        assert r["error"] == "not_found"

    def test_update_nonexistent_node(self, mcp: ToolCatalog) -> None:
        r = _call(mcp, "graph_update_node", node_id="ghost", properties={"x": 1})
        assert r["error"] == "not_found"

    def test_delete_nonexistent_node(self, mcp: ToolCatalog) -> None:
        assert _call(mcp, "graph_delete_node", node_id="nope")["deleted"] is False

    def test_delete_nonexistent_edge(self, mcp: ToolCatalog) -> None:
        assert _call(mcp, "graph_delete_edge", edge_id="nope")["deleted"] is False

    def test_get_edges_isolated_node(self, mcp: ToolCatalog) -> None:
        n = _call(mcp, "graph_add_node", labels=["Isolated"], properties={})
        r = _call(mcp, "graph_get_edges", node_id=n["id"])
        assert r["count"] == 0

    def test_add_edge_without_properties(self, mcp: ToolCatalog) -> None:
        a = _call(mcp, "graph_add_node", labels=["A"], properties={})
        b = _call(mcp, "graph_add_node", labels=["B"], properties={})
        e = _call(mcp, "graph_add_edge", source_id=a["id"], target_id=b["id"],
                   edge_type="PLAIN")
        assert e["properties"] == {}

    def test_query_empty_graph(self, mcp: ToolCatalog) -> None:
        r = _call(mcp, "graph_query", cypher="MATCH (n) RETURN n")
        assert r["nodes"] == []

    def test_delete_node_cascades_edges(self, mcp: ToolCatalog) -> None:
        a = _call(mcp, "graph_add_node", labels=["A"], properties={})
        b = _call(mcp, "graph_add_node", labels=["B"], properties={})
        _call(mcp, "graph_add_edge", source_id=a["id"], target_id=b["id"],
              edge_type="LINK")
        _call(mcp, "graph_delete_node", node_id=a["id"])
        r = _call(mcp, "graph_get_edges", node_id=b["id"])
        assert r["count"] == 0

    def test_digraph_overwrites_duplicate_edge(self, mcp: ToolCatalog) -> None:
        a = _call(mcp, "graph_add_node", labels=["A"], properties={})
        b = _call(mcp, "graph_add_node", labels=["B"], properties={})
        _call(mcp, "graph_add_edge", source_id=a["id"], target_id=b["id"],
              edge_type="FIRST", properties={"order": 1})
        _call(mcp, "graph_add_edge", source_id=a["id"], target_id=b["id"],
              edge_type="SECOND", properties={"order": 2})
        r = _call(mcp, "graph_get_edges", node_id=a["id"], direction="out")
        assert r["count"] == 1
        assert r["edges"][0]["type"] == "SECOND"

    def test_get_edges_direction_both(self, mcp: ToolCatalog) -> None:
        a = _call(mcp, "graph_add_node", labels=["A"], properties={})
        b = _call(mcp, "graph_add_node", labels=["B"], properties={})
        c = _call(mcp, "graph_add_node", labels=["C"], properties={})
        _call(mcp, "graph_add_edge", source_id=a["id"], target_id=b["id"],
              edge_type="OUT")
        _call(mcp, "graph_add_edge", source_id=c["id"], target_id=b["id"],
              edge_type="IN")
        r = _call(mcp, "graph_get_edges", node_id=b["id"], direction="both")
        assert r["count"] == 2

    def test_update_merges_properties(self, mcp: ToolCatalog) -> None:
        n = _call(mcp, "graph_add_node", labels=["Doc"],
                   properties={"path": "a.md", "format": "md"})
        u = _call(mcp, "graph_update_node", node_id=n["id"],
                   properties={"reviewed": True})
        assert u["properties"]["path"] == "a.md"
        assert u["properties"]["reviewed"] is True

    def test_double_delete_node(self, mcp: ToolCatalog) -> None:
        n = _call(mcp, "graph_add_node", labels=["Temp"], properties={})
        assert _call(mcp, "graph_delete_node", node_id=n["id"])["deleted"]
        assert not _call(mcp, "graph_delete_node", node_id=n["id"])["deleted"]

    def test_double_delete_edge(self, mcp: ToolCatalog) -> None:
        a = _call(mcp, "graph_add_node", labels=["A"], properties={})
        b = _call(mcp, "graph_add_node", labels=["B"], properties={})
        e = _call(mcp, "graph_add_edge", source_id=a["id"], target_id=b["id"],
                   edge_type="E")
        assert _call(mcp, "graph_delete_edge", edge_id=e["id"])["deleted"]
        assert not _call(mcp, "graph_delete_edge", edge_id=e["id"])["deleted"]
