"""E2E tests: full CRUD lifecycle and step isolation.

Part 2 of the graph E2E suite — exercises the complete graph CRUD
lifecycle through MCP tools, then tests each step in isolation.
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


# ── Full Lifecycle (Recipe Step 9) ──────────────────────────────────


class TestGraphE2ELifecycle:
    """Full CRUD lifecycle following data-layer recipe Step 9."""

    def test_full_lifecycle(self, mcp: ToolCatalog) -> None:
        # 9a. Add Document node
        doc = _call(mcp, "graph_add_node", labels=["Document"],
                     properties={"path": "docs/readme.md", "format": "markdown"})
        assert doc["labels"] == ["Document"]
        doc_id = doc["id"]

        # 9b. Add Project node
        proj = _call(mcp, "graph_add_node", labels=["Project"],
                      properties={"name": "python-factory"})
        proj_id = proj["id"]

        # 9c. Connect with BELONGS_TO edge
        edge = _call(mcp, "graph_add_edge", source_id=doc_id,
                      target_id=proj_id, edge_type="BELONGS_TO",
                      properties={"added_by": "e2e-test"})
        assert edge["type"] == "BELONGS_TO"
        edge_id = edge["id"]

        # 9d. Query edges (direction=out)
        edges = _call(mcp, "graph_get_edges", node_id=doc_id, direction="out")
        assert edges["count"] == 1
        assert edges["edges"][0]["type"] == "BELONGS_TO"

        # 9e. Cypher query
        qr = _call(mcp, "graph_query", cypher="MATCH (n) RETURN n")
        assert len(qr["nodes"]) >= 2

        # 9f. Verify node retrieval
        got = _call(mcp, "graph_get_node", node_id=doc_id)
        assert got["properties"]["path"] == "docs/readme.md"

        # 9g. Update node properties
        upd = _call(mcp, "graph_update_node", node_id=doc_id,
                     properties={"path": "docs/readme.md", "format": "markdown",
                                 "reviewed": True})
        assert upd["properties"]["reviewed"] is True

        # 9h. Clean up
        assert _call(mcp, "graph_delete_edge", edge_id=edge_id)["deleted"]
        assert _call(mcp, "graph_delete_node", node_id=doc_id)["deleted"]
        assert _call(mcp, "graph_delete_node", node_id=proj_id)["deleted"]

        # Verify deleted node returns not_found
        gone = _call(mcp, "graph_get_node", node_id=doc_id)
        assert gone["error"] == "not_found"


# ── Step Isolation Tests ────────────────────────────────────────────


class TestGraphE2EStepIsolation:
    """Each recipe step tested in isolation for precise failure diagnosis."""

    def test_9a_add_document_node(self, mcp: ToolCatalog) -> None:
        r = _call(mcp, "graph_add_node", labels=["Document"],
                   properties={"path": "docs/readme.md", "format": "markdown"})
        assert r["labels"] == ["Document"]
        assert r["properties"]["path"] == "docs/readme.md"

    def test_9b_add_project_node(self, mcp: ToolCatalog) -> None:
        r = _call(mcp, "graph_add_node", labels=["Project"],
                   properties={"name": "python-factory"})
        assert r["labels"] == ["Project"]

    def test_9c_add_edge(self, mcp: ToolCatalog) -> None:
        d = _call(mcp, "graph_add_node", labels=["Document"], properties={"p": "x"})
        p = _call(mcp, "graph_add_node", labels=["Project"], properties={"n": "y"})
        e = _call(mcp, "graph_add_edge", source_id=d["id"], target_id=p["id"],
                   edge_type="BELONGS_TO", properties={"added_by": "e2e-test"})
        assert e["type"] == "BELONGS_TO"

    def test_9d_get_edges_out(self, mcp: ToolCatalog) -> None:
        d = _call(mcp, "graph_add_node", labels=["D"], properties={})
        p = _call(mcp, "graph_add_node", labels=["P"], properties={})
        _call(mcp, "graph_add_edge", source_id=d["id"], target_id=p["id"],
              edge_type="BELONGS_TO")
        r = _call(mcp, "graph_get_edges", node_id=d["id"], direction="out")
        assert r["count"] == 1

    def test_9d_get_edges_in(self, mcp: ToolCatalog) -> None:
        d = _call(mcp, "graph_add_node", labels=["D"], properties={})
        p = _call(mcp, "graph_add_node", labels=["P"], properties={})
        _call(mcp, "graph_add_edge", source_id=d["id"], target_id=p["id"],
              edge_type="BELONGS_TO")
        r = _call(mcp, "graph_get_edges", node_id=p["id"], direction="in")
        assert r["count"] == 1

    def test_9e_cypher_query(self, mcp: ToolCatalog) -> None:
        _call(mcp, "graph_add_node", labels=["A"], properties={})
        _call(mcp, "graph_add_node", labels=["B"], properties={})
        r = _call(mcp, "graph_query", cypher="MATCH (n) RETURN n")
        assert len(r["nodes"]) == 2

    def test_9f_get_node(self, mcp: ToolCatalog) -> None:
        a = _call(mcp, "graph_add_node", labels=["Doc"],
                   properties={"path": "docs/readme.md"})
        g = _call(mcp, "graph_get_node", node_id=a["id"])
        assert g["properties"]["path"] == "docs/readme.md"

    def test_9g_update_node(self, mcp: ToolCatalog) -> None:
        a = _call(mcp, "graph_add_node", labels=["Doc"],
                   properties={"path": "x", "format": "md"})
        u = _call(mcp, "graph_update_node", node_id=a["id"],
                   properties={"path": "x", "format": "md", "reviewed": True})
        assert u["properties"]["reviewed"] is True

    def test_9h_delete_edge(self, mcp: ToolCatalog) -> None:
        a = _call(mcp, "graph_add_node", labels=["A"], properties={})
        b = _call(mcp, "graph_add_node", labels=["B"], properties={})
        e = _call(mcp, "graph_add_edge", source_id=a["id"], target_id=b["id"],
                   edge_type="R")
        assert _call(mcp, "graph_delete_edge", edge_id=e["id"])["deleted"]

    def test_9h_delete_node(self, mcp: ToolCatalog) -> None:
        n = _call(mcp, "graph_add_node", labels=["Temp"], properties={})
        assert _call(mcp, "graph_delete_node", node_id=n["id"])["deleted"]

    def test_deleted_node_returns_not_found(self, mcp: ToolCatalog) -> None:
        n = _call(mcp, "graph_add_node", labels=["Temp"], properties={})
        _call(mcp, "graph_delete_node", node_id=n["id"])
        r = _call(mcp, "graph_get_node", node_id=n["id"])
        assert r["error"] == "not_found"
        assert r["node_id"] == n["id"]
        assert r["found"] is False
