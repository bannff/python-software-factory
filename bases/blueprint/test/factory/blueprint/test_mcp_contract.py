"""Tests for Blueprint MCP contract tools."""
from __future__ import annotations

import asyncio

from factory.blueprint.server import get_mcp_server


def _get_tool(name: str):
    return asyncio.run(get_mcp_server().get_tool(name))


class TestGetCapabilities:
    def test_tool_registered(self) -> None:
        assert _get_tool("blueprint_get_capabilities") is not None

    def test_returns_typed_envelope(self) -> None:
        result = _get_tool("blueprint_get_capabilities").fn()
        assert result.ok is True
        assert result.data.name == "blueprint"
        assert result.data.type == "base"
        assert result.data.services


class TestHealthCheck:
    def test_tool_registered(self) -> None:
        assert _get_tool("blueprint_health_check") is not None

    def test_has_healthy_field(self) -> None:
        result = _get_tool("blueprint_health_check").fn()
        assert result.ok is True
        assert isinstance(result.data.healthy, bool)


class TestDescribeConfigSchema:
    def test_tool_registered(self) -> None:
        assert _get_tool("blueprint_describe_config_schema") is not None

    def test_has_type_field(self) -> None:
        result = _get_tool("blueprint_describe_config_schema").fn()
        assert result.ok is True
        assert result.data.type == "object"


class TestListServices:
    def test_tool_registered(self) -> None:
        assert _get_tool("blueprint_list_services") is not None

    def test_has_services(self) -> None:
        result = _get_tool("blueprint_list_services").fn()
        assert result.ok is True
        assert result.data.services
        assert result.data.urls
