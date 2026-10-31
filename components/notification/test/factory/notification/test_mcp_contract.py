"""Tests for notification MCP contract tools.

Every MCP-enabled brick MUST expose:
- get_capabilities() - Machine-readable feature list
- health_check() - Fast readiness probe
- describe_config_schema() - JSON schema for configuration
"""

from __future__ import annotations

import asyncio

import pytest

from factory.notification.server import create_mcp_server
from factory.notification.runtime.dispatcher import NotificationRuntime


@pytest.fixture
def runtime(tmp_path) -> NotificationRuntime:
    """Create a test runtime with temp directory."""
    return NotificationRuntime(config_dir=tmp_path)


@pytest.fixture
def mcp(runtime):
    """Create MCP server with test runtime."""
    return create_mcp_server(runtime)


def _get_tool(mcp, name: str):
    """Get a tool by name from the MCP server."""
    return asyncio.run(mcp.get_tool(name))


class TestGetCapabilities:
    """Tests for get_capabilities contract tool."""

    def test_tool_registered(self, mcp) -> None:
        """get_capabilities tool must be registered."""
        tool = _get_tool(mcp, "get_capabilities")
        assert tool is not None

    def test_returns_dict(self, mcp, runtime) -> None:
        """get_capabilities must return a dictionary."""
        result = runtime.get_capabilities()
        assert isinstance(result, dict)

    def test_has_name(self, mcp, runtime) -> None:
        """Capabilities must include brick name."""
        result = runtime.get_capabilities()
        assert "module" in result or "name" in result

    def test_has_version(self, mcp, runtime) -> None:
        """Capabilities must include version."""
        result = runtime.get_capabilities()
        assert "version" in result


class TestHealthCheck:
    """Tests for health_check contract tool."""

    def test_tool_registered(self, mcp) -> None:
        """health_check tool must be registered."""
        tool = _get_tool(mcp, "health_check")
        assert tool is not None

    @pytest.mark.asyncio
    async def test_returns_dict(self, mcp, runtime) -> None:
        """health_check must return a dictionary."""
        result = await runtime.health_check()
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_has_ok_field(self, mcp, runtime) -> None:
        """health_check must include ok status."""
        result = await runtime.health_check()
        assert "ok" in result
        assert isinstance(result["ok"], bool)


class TestDescribeConfigSchema:
    """Tests for describe_config_schema contract tool."""

    def test_tool_registered(self, mcp) -> None:
        """describe_config_schema tool must be registered."""
        tool = _get_tool(mcp, "describe_config_schema")
        assert tool is not None

    def test_returns_dict(self, mcp, runtime) -> None:
        """describe_config_schema must return a dictionary."""
        result = runtime.describe_config_schema()
        assert isinstance(result, dict)

    def test_has_schema_version(self, mcp, runtime) -> None:
        """Schema must have schema_version field."""
        result = runtime.describe_config_schema()
        assert "schema_version" in result

    def test_has_schemas(self, mcp, runtime) -> None:
        """Schema must have schemas field."""
        result = runtime.describe_config_schema()
        assert "schemas" in result
