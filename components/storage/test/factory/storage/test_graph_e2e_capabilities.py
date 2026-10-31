"""E2E tests: graph capabilities, config schema, and health check.

Part 1 of the graph E2E suite — validates that the storage brick
correctly advertises graph support in its MCP surface.
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


# ── Capabilities ────────────────────────────────────────────────────


class TestGraphCapabilities:
    """Verify get_capabilities advertises graph support."""

    def test_storage_types_includes_graph(self, mcp: ToolCatalog) -> None:
        result = _call(mcp, "get_capabilities")
        assert "graph" in result["storage_types"]

    def test_features_includes_graph_storage(self, mcp: ToolCatalog) -> None:
        result = _call(mcp, "get_capabilities")
        assert "graph_storage" in result["features"]

    def test_backends_includes_graph(self, mcp: ToolCatalog) -> None:
        result = _call(mcp, "get_capabilities")
        assert "graph" in result["backends"]
        assert "networkx" in result["backends"]["graph"]
        assert "neo4j" in result["backends"]["graph"]


# ── Config Schema ───────────────────────────────────────────────────


class TestGraphConfigSchema:
    """Verify describe_config_schema includes graph backend config."""

    def test_schema_includes_graph_section(self, mcp: ToolCatalog) -> None:
        result = _call(mcp, "describe_config_schema")
        assert "graph" in result["properties"]

    def test_graph_backend_enum(self, mcp: ToolCatalog) -> None:
        result = _call(mcp, "describe_config_schema")
        graph_props = result["properties"]["graph"]["properties"]
        assert "backend" in graph_props
        assert "networkx" in graph_props["backend"]["enum"]
        assert "neo4j" in graph_props["backend"]["enum"]


# ── Health Check ────────────────────────────────────────────────────


class TestGraphHealthCheck:
    """Verify storage brick health check works."""

    def test_health_check_healthy(self, mcp: ToolCatalog) -> None:
        result = _call(mcp, "health_check")
        assert result["healthy"] is True

    def test_health_check_with_graph_store(
        self, mcp: ToolCatalog, runtime: StorageRuntime
    ) -> None:
        runtime.get_graph_store("networkx")
        result = _call(mcp, "health_check")
        assert result["healthy"] is True
        assert len(result["stores"]) >= 1
