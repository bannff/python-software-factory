"""Tests for aggregator resource/prompt delegation methods."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from factory.mcp_server.runtime.aggregator import MCPAggregator


def _make_aggregator():
    return MCPAggregator(MagicMock())


def _setup_with_brick(brick_name="test_brick"):
    mock_catalog = MagicMock()
    mock_catalog.tool_map.return_value = {}
    mock_module = SimpleNamespace(create_tool_catalog=lambda: mock_catalog)
    with patch(
        "factory.mcp_server.runtime.lazy_loader.importlib.import_module",
        return_value=mock_module,
    ):
        agg = _make_aggregator()
        agg.set_available_bricks([brick_name])
        agg._lazy.ensure_loaded(brick_name)
    return agg, mock_catalog


class TestLazyOrError:
    def test_returns_error_when_not_initialized(self):
        agg = _make_aggregator()
        mcp, err = agg._lazy_or_error("any")
        assert mcp is None and err == "Progressive mode not initialized"

    def test_returns_mcp_for_known_brick(self):
        agg, mock_mcp = _setup_with_brick("config")
        mcp, err = agg._lazy_or_error("config")
        assert mcp is mock_mcp and err is None

    def test_returns_error_for_unknown_brick(self):
        agg = _make_aggregator()
        agg.set_available_bricks([])
        mcp, err = agg._lazy_or_error("ghost")
        assert mcp is None and "Unknown brick" in err


class TestGetBrickResources:
    def test_returns_error_when_not_initialized(self):
        assert _make_aggregator().get_brick_resources("any") == {
            "error": "Progressive mode not initialized"}

    def test_delegates_to_primitives(self):
        agg, mock_mcp = _setup_with_brick("config")
        mock_res = MagicMock()
        mock_res.uri, mock_res.name, mock_res.description = (
            "config://aws/identity", "aws_id", "AWS identity")
        mock_mcp.list_resources = AsyncMock(return_value=[mock_res])
        mock_mcp.list_resource_templates = AsyncMock(return_value=[])
        result = agg.get_brick_resources("config")
        assert result["brick"] == "config" and result["count"] == 1

    def test_returns_error_for_unknown_brick(self):
        agg = _make_aggregator()
        agg.set_available_bricks([])
        assert "error" in agg.get_brick_resources("ghost")


class TestGetBrickPrompts:
    def test_returns_error_when_not_initialized(self):
        assert _make_aggregator().get_brick_prompts("any") == {
            "error": "Progressive mode not initialized"}

    def test_delegates_to_primitives(self):
        agg, mock_mcp = _setup_with_brick("graph")
        mock_arg = MagicMock()
        mock_arg.name, mock_arg.description, mock_arg.required = "q", "Query", True
        mock_prompt = MagicMock()
        mock_prompt.name, mock_prompt.description = "search", "Search"
        mock_prompt.arguments = [mock_arg]
        mock_mcp.list_prompts = AsyncMock(return_value=[mock_prompt])
        result = agg.get_brick_prompts("graph")
        assert result["brick"] == "graph" and result["count"] == 1


class TestReadBrickResource:
    def test_returns_error_when_not_initialized(self):
        result = asyncio.run(_make_aggregator().read_brick_resource("any", "uri://x"))
        assert result == {"error": "Progressive mode not initialized"}

    def test_delegates_to_primitives(self):
        agg, mock_mcp = _setup_with_brick("config")
        mock_content = MagicMock()
        mock_content.content, mock_content.mime_type = "data", "application/json"
        mock_result = MagicMock()
        mock_result.contents = [mock_content]
        mock_mcp.read_resource = AsyncMock(return_value=mock_result)
        result = asyncio.run(agg.read_brick_resource("config", "config://aws/identity"))
        assert result["uri"] == "config://aws/identity"

    def test_returns_error_on_failure(self):
        agg, mock_mcp = _setup_with_brick("config")
        mock_mcp.read_resource = AsyncMock(side_effect=RuntimeError("connection lost"))
        result = asyncio.run(agg.read_brick_resource("config", "config://broken"))
        assert "error" in result


class TestRenderBrickPrompt:
    def test_returns_error_when_not_initialized(self):
        result = asyncio.run(_make_aggregator().render_brick_prompt("any", "p", {}))
        assert result == {"error": "Progressive mode not initialized"}

    def test_delegates_to_primitives(self):
        agg, mock_mcp = _setup_with_brick("kb")
        mock_msg = MagicMock()
        mock_msg.role = "assistant"
        mock_msg.content = MagicMock()
        mock_msg.content.text = "Here are results"
        mock_result = MagicMock()
        mock_result.messages = [mock_msg]
        mock_mcp.render_prompt = AsyncMock(return_value=mock_result)
        result = asyncio.run(agg.render_brick_prompt("kb", "search", {"q": "test"}))
        assert result["prompt"] == "search"

    def test_passes_none_arguments(self):
        agg, mock_mcp = _setup_with_brick("kb")
        mock_msg = MagicMock()
        mock_msg.role, mock_msg.content = "system", MagicMock()
        mock_msg.content.text = "Default"
        mock_result = MagicMock()
        mock_result.messages = [mock_msg]
        mock_mcp.render_prompt = AsyncMock(return_value=mock_result)
        asyncio.run(agg.render_brick_prompt("kb", "default", None))
        mock_mcp.render_prompt.assert_called_once_with("default", arguments={})

    def test_returns_error_on_failure(self):
        agg, mock_mcp = _setup_with_brick("kb")
        mock_mcp.render_prompt = AsyncMock(side_effect=KeyError("no such prompt"))
        result = asyncio.run(agg.render_brick_prompt("kb", "missing", {}))
        assert "error" in result
