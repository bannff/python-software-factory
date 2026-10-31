"""Tests for integrations brick MCP contract compliance."""

from __future__ import annotations

import pytest

from factory.integrations.interface import Runtime, create_server


class TestMCPContract:
    """Verify integrations brick meets MCP contract requirements."""

    def test_create_server(self) -> None:
        """Test MCP server creation."""
        server = create_server()
        assert server is not None
        assert server.name == "integrations-module"

    def test_interface_exports(self) -> None:
        """Test interface exports Runtime and create_server."""
        from factory.integrations import interface

        assert hasattr(interface, "Runtime")
        assert hasattr(interface, "create_server")
        assert callable(interface.create_server)

    def test_runtime_has_health_check(self) -> None:
        """Test runtime exposes health_check method."""
        runtime = Runtime()
        health = runtime.health_check()

        assert health.healthy is True
        assert health.connector_count == 0

    def test_runtime_has_settings(self) -> None:
        """Test runtime exposes settings for config schema."""
        runtime = Runtime()
        settings = runtime.settings

        assert settings.service_name == "integrations-module"


class TestRuntimeCapabilities:
    """Test runtime provides required capabilities."""

    def test_register_capability(self) -> None:
        """Test runtime can register connectors."""
        runtime = Runtime()
        connector = runtime.register(
            connector_id="test",
            name="Test API",
            base_url="https://example.com",
        )
        assert connector.config.id == "test"

    def test_connect_capability(self) -> None:
        """Test runtime can connect connectors."""
        runtime = Runtime()
        runtime.register("test", "Test", "https://example.com")

        assert runtime.connect("test") is True

    def test_call_capability(self) -> None:
        """Test runtime can make calls (returns error when not connected)."""
        runtime = Runtime()
        runtime.register("test", "Test", "https://example.com")

        result = runtime.call("test", "GET", "/path")
        # Not connected, so should fail
        assert result.success is False

    def test_list_capability(self) -> None:
        """Test runtime can list connectors."""
        runtime = Runtime()
        runtime.register("test1", "Test 1", "https://example1.com")
        runtime.register("test2", "Test 2", "https://example2.com")

        connectors = runtime.list_connectors()
        assert len(connectors) == 2

    def test_unregister_capability(self) -> None:
        """Test runtime can unregister connectors."""
        runtime = Runtime()
        runtime.register("test", "Test", "https://example.com")

        assert runtime.unregister("test") is True
        assert runtime.get("test") is None
