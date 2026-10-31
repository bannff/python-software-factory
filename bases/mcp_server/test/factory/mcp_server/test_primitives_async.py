"""Tests for async brick primitives (read_resource, render_prompt)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from factory.mcp_server.runtime.primitives import read_resource, render_prompt


def _mock_content(content="hello", mime_type="text/plain"):
    c = MagicMock()
    c.content, c.mime_type = content, mime_type
    return c


def _mock_message(role="user", text="Hi"):
    m = MagicMock()
    m.role = role
    m.content = MagicMock()
    m.content.text = text
    return m


class TestReadResource:
    def test_reads_resource_successfully(self):
        content = _mock_content("data here", "application/json")
        mock_result = MagicMock()
        mock_result.contents = [content]
        mock_mcp = MagicMock()
        mock_mcp.read_resource = AsyncMock(return_value=mock_result)
        result = asyncio.run(read_resource(mock_mcp, "config://test"))
        assert result["uri"] == "config://test"
        assert result["contents"][0]["content"] == "data here"

    def test_returns_error_on_exception(self):
        mock_mcp = MagicMock()
        mock_mcp.read_resource = AsyncMock(side_effect=ValueError("Not found"))
        result = asyncio.run(read_resource(mock_mcp, "config://missing"))
        assert "error" in result

    def test_content_without_mime_type_attr(self):
        content = MagicMock(spec=[])
        content.content = "raw"
        mock_result = MagicMock()
        mock_result.contents = [content]
        mock_mcp = MagicMock()
        mock_mcp.read_resource = AsyncMock(return_value=mock_result)
        result = asyncio.run(read_resource(mock_mcp, "res://raw"))
        assert result["contents"][0]["mime_type"] == "text/plain"

    def test_none_result(self):
        mock_mcp = MagicMock()
        mock_mcp.read_resource = AsyncMock(return_value=None)
        result = asyncio.run(read_resource(mock_mcp, "res://none"))
        assert result["contents"] == []


class TestRenderPrompt:
    def test_renders_prompt_successfully(self):
        msg = _mock_message("assistant", "Here is your answer")
        mock_result = MagicMock()
        mock_result.messages = [msg]
        mock_mcp = MagicMock()
        mock_mcp.render_prompt = AsyncMock(return_value=mock_result)
        result = asyncio.run(render_prompt(mock_mcp, "search", {"query": "test"}))
        assert result["prompt"] == "search"
        assert result["messages"][0]["content"] == "Here is your answer"

    def test_renders_with_no_arguments(self):
        msg = _mock_message("system", "Default")
        mock_result = MagicMock()
        mock_result.messages = [msg]
        mock_mcp = MagicMock()
        mock_mcp.render_prompt = AsyncMock(return_value=mock_result)
        asyncio.run(render_prompt(mock_mcp, "default_prompt", None))
        mock_mcp.render_prompt.assert_called_once_with("default_prompt", arguments={})

    def test_returns_error_on_exception(self):
        mock_mcp = MagicMock()
        mock_mcp.render_prompt = AsyncMock(side_effect=KeyError("no such prompt"))
        result = asyncio.run(render_prompt(mock_mcp, "missing_prompt"))
        assert "error" in result

    def test_none_result(self):
        mock_mcp = MagicMock()
        mock_mcp.render_prompt = AsyncMock(return_value=None)
        result = asyncio.run(render_prompt(mock_mcp, "none_prompt"))
        assert result["messages"] == []
