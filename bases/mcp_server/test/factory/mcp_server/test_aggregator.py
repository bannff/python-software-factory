"""Tests for MCP aggregator.

Tests the MCPAggregator class which dynamically imports and aggregates
tools from multiple brick MCP servers into a unified FastMCP instance.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from factory.mcp_server import MCPAggregator
from factory.mcp_server.runtime.aggregator import BrickRegistration

from .typed_tool_fixtures import add_empty_tool


class TestBrickRegistration:
    """Tests for BrickRegistration dataclass."""

    def test_registration_creation(self):
        """BrickRegistration should store all fields."""
        reg = BrickRegistration(
            name="test",
            namespace="factory.test",
            tools_count=5,
            healthy=True,
        )
        assert reg.name == "test"
        assert reg.tools_count == 5
        assert reg.healthy is True
        assert reg.error is None

    def test_registration_with_error(self):
        """BrickRegistration should store error info."""
        reg = BrickRegistration(
            name="broken",
            namespace="factory.broken",
            tools_count=0,
            healthy=False,
            error="Import failed",
        )
        assert reg.healthy is False
        assert reg.error == "Import failed"


class TestMCPAggregator:
    """Tests for MCPAggregator class."""

    def test_aggregator_init(self):
        """Aggregator should initialize with FastMCP instance."""
        mock_mcp = MagicMock()
        aggregator = MCPAggregator(mock_mcp)

        assert aggregator.mcp is mock_mcp
        assert aggregator._registered == {}

    def test_aggregator_handles_import_error(self):
        """Should handle missing brick gracefully."""
        mock_mcp = MagicMock()
        aggregator = MCPAggregator(mock_mcp)

        result = aggregator.register_brick("nonexistent_brick_xyz")

        assert result is False
        assert "nonexistent_brick_xyz" in aggregator._registered
        assert aggregator._registered["nonexistent_brick_xyz"].healthy is False

    def test_aggregated_capabilities_empty(self):
        """Should return proper structure with no bricks."""
        mock_mcp = MagicMock()
        aggregator = MCPAggregator(mock_mcp)

        caps = aggregator.get_aggregated_capabilities()

        assert caps["server"] == "factory-aggregator"
        assert caps["registered_bricks"] == 0
        assert caps["total_tools"] == 0
        assert caps["bricks"] == {}

    def test_aggregated_health_check_empty(self):
        """Should check health with no registered bricks."""
        mock_mcp = MagicMock()
        aggregator = MCPAggregator(mock_mcp)

        health = aggregator.aggregated_health_check()

        assert health["status"] == "healthy"
        assert health["healthy_bricks"] == 0
        assert health["total_bricks"] == 0

    def test_register_all(self):
        """Should register multiple bricks and return results."""
        mock_mcp = MagicMock()
        aggregator = MCPAggregator(mock_mcp)

        # These will fail to import but should be handled gracefully
        results = aggregator.register_all(["fake_brick_1", "fake_brick_2"])

        assert "fake_brick_1" in results
        assert "fake_brick_2" in results
        assert results["fake_brick_1"] is False
        assert results["fake_brick_2"] is False

    @patch("factory.mcp_server.runtime.aggregator.importlib.import_module")
    def test_aggregator_registers_brick_success(self, mock_import):
        """Aggregator registers a neutral brick catalog."""
        from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

        catalog = ToolCatalog("test")
        mock_import.return_value = SimpleNamespace(create_tool_catalog=lambda: catalog)
        aggregator = MCPAggregator()
        assert aggregator.register_brick("test_brick") is True
        assert aggregator._registered["test_brick"].healthy is True

class TestParseToolName:
    """Tests for _parse_tool_name alias resolution."""

    def _make_aggregator(self, bricks: list[str]) -> MCPAggregator:
        mock_mcp = MagicMock()
        agg = MCPAggregator(mock_mcp)
        agg._registered = {b: BrickRegistration(b, f"factory.{b}", 1) for b in bricks}
        return agg

    def test_exact_prefix_match(self):
        agg = self._make_aggregator(["metrics", "evals"])
        assert agg._parse_tool_name("metrics_get_views") == ("metrics", "get_views")

    def test_ml_alias_resolves_to_machine_learning(self):
        agg = self._make_aggregator(["machine_learning", "metrics"])
        brick, local = agg._parse_tool_name("ml_get_views")
        assert brick == "machine_learning"
        assert local == "ml_get_views"

    def test_unknown_prefix_returns_none(self):
        agg = self._make_aggregator(["metrics"])
        assert agg._parse_tool_name("unknown_tool") == (None, None)


def test_aggregator_accepts_neutral_catalog_without_mount(monkeypatch) -> None:
    """Native composition collects tools without a FastMCP root server."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
    catalog = ToolCatalog("demo")

    add_empty_tool(catalog, "demo_ping")

    module = MagicMock(create_tool_catalog=lambda: catalog)
    monkeypatch.setattr(
        "factory.mcp_server.runtime.aggregator.importlib.import_module",
        lambda _name: module,
    )
    aggregator = MCPAggregator()

    assert aggregator.register_brick("demo") is True
    assert aggregator._flat_bricks["demo"] is catalog
    assert aggregator.get_brick_tool_names("demo") == ["demo_ping"]


def test_canonical_resolver_matches_native_catalog_and_suggests_typos() -> None:
    """REST, native callbacks, and discovery share one public-name resolver."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
    aggregator = MCPAggregator()
    aggregator.set_available_bricks(["evals", "graph"])
    for brick, tool_name in (
        ("evals", "evals_get_dashboard_summary"),
        ("graph", "graph_find_entities"),
    ):
        catalog = ToolCatalog(brick)

        add_empty_tool(catalog, tool_name)
        aggregator._lazy._cache[brick] = catalog

    discovered = set(aggregator.get_all_tool_names())
    from factory.mcp_server.runtime.selected_tools import resolve_selected_tools
    from factory.mcp_server.runtime.tool_catalog import build_tool_catalog
    native_names = {
        item.public_name for item in resolve_selected_tools(
            aggregator, None, rename_dot_to_underscore=True,
        )
    }
    catalog_names = {
        item["qualified_name"] for item in build_tool_catalog(aggregator)["tools"]
    }
    assert discovered == native_names == catalog_names == {
        "evals_get_dashboard_summary", "graph_find_entities",
    }
    for name in discovered:
        resolution = aggregator.resolve_tool_name(name)
        assert resolution.found
        assert resolution.canonical_name == name

    missing = aggregator.resolve_tool_name("graph_find_entites")
    assert not missing.found
    assert missing.suggestions[0] == "graph_find_entities"
