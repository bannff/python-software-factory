"""Tests for integrations runtime core functionality."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from factory.integrations.core import ConnectorStatus
from factory.integrations.runtime.adapters.rest import RestConnector
from factory.integrations.runtime.models import ConnectorConfig, Settings
from factory.integrations.runtime.runtime import IntegrationsRuntime


class TestRestConnector:
    """Tests for REST connector adapter."""

    def test_create_connector(self) -> None:
        """Test creating a REST connector."""
        config = ConnectorConfig(
            id="test",
            name="Test API",
            connector_type="rest",
            base_url="https://api.example.com",
        )
        connector = RestConnector(config)

        assert connector.config.id == "test"
        assert connector.status == ConnectorStatus.DISCONNECTED

    def test_connect_disconnect(self) -> None:
        """Test connect and disconnect lifecycle."""
        config = ConnectorConfig(
            id="test",
            name="Test API",
            connector_type="rest",
            base_url="https://api.example.com",
        )
        connector = RestConnector(config)

        # Connect
        assert connector.connect() is True
        assert connector.is_connected() is True
        assert connector.status == ConnectorStatus.CONNECTED

        # Disconnect
        connector.disconnect()
        assert connector.is_connected() is False
        assert connector.status == ConnectorStatus.DISCONNECTED

    def test_call_without_connection(self) -> None:
        """Test calling without connecting first."""
        config = ConnectorConfig(
            id="test",
            name="Test API",
            connector_type="rest",
            base_url="https://api.example.com",
        )
        connector = RestConnector(config)

        result = connector.call("GET", "/test")
        assert result.success is False
        assert "Not connected" in result.error

    def test_health_check(self) -> None:
        """Test health check."""
        config = ConnectorConfig(
            id="test",
            name="Test API",
            connector_type="rest",
            base_url="https://api.example.com",
        )
        connector = RestConnector(config)

        health = connector.health_check()
        assert health.healthy is False  # Not connected

        connector.connect()
        health = connector.health_check()
        assert health.healthy is True

        connector.disconnect()

    def test_to_connector_model(self) -> None:
        """Test converting to Connector model."""
        config = ConnectorConfig(
            id="test",
            name="Test API",
            connector_type="rest",
            base_url="https://api.example.com",
        )
        connector = RestConnector(config)
        model = connector.to_connector()

        assert model.config.id == "test"
        assert model.status == ConnectorStatus.DISCONNECTED


class TestIntegrationsRuntime:
    """Tests for integrations runtime."""

    def test_default_initialization(self) -> None:
        """Test runtime initializes with defaults."""
        runtime = IntegrationsRuntime()
        assert runtime.settings.service_name == "integrations-module"

    def test_register_connector(self) -> None:
        """Test registering a connector."""
        runtime = IntegrationsRuntime()

        connector = runtime.register(
            connector_id="github",
            name="GitHub API",
            base_url="https://api.github.com",
        )

        assert connector.config.id == "github"
        assert connector.config.name == "GitHub API"

    def test_unregister_connector(self) -> None:
        """Test unregistering a connector."""
        runtime = IntegrationsRuntime()
        runtime.register("test", "Test", "https://example.com")

        assert runtime.unregister("test") is True
        assert runtime.unregister("test") is False  # Already removed
        assert runtime.get("test") is None

    def test_list_connectors(self) -> None:
        """Test listing connectors."""
        runtime = IntegrationsRuntime()
        runtime.register("api1", "API 1", "https://api1.example.com")
        runtime.register("api2", "API 2", "https://api2.example.com")

        connectors = runtime.list_connectors()
        assert len(connectors) == 2

    def test_connect_and_disconnect(self) -> None:
        """Test connect and disconnect operations."""
        runtime = IntegrationsRuntime()
        runtime.register("test", "Test", "https://example.com")

        assert runtime.connect("test") is True
        connector = runtime.get("test")
        assert connector.status == ConnectorStatus.CONNECTED

        assert runtime.disconnect("test") is True
        connector = runtime.get("test")
        assert connector.status == ConnectorStatus.DISCONNECTED

    def test_connect_nonexistent(self) -> None:
        """Test connecting nonexistent connector."""
        runtime = IntegrationsRuntime()
        assert runtime.connect("nonexistent") is False

    def test_call_nonexistent(self) -> None:
        """Test calling nonexistent connector."""
        runtime = IntegrationsRuntime()
        result = runtime.call("nonexistent", "GET", "/test")

        assert result.success is False
        assert "not found" in result.error

    def test_health_check(self) -> None:
        """Test overall health check."""
        runtime = IntegrationsRuntime()
        runtime.register("api1", "API 1", "https://api1.example.com")
        runtime.register("api2", "API 2", "https://api2.example.com")

        health = runtime.health_check()
        assert health.connector_count == 2
        assert health.connected_count == 0

        runtime.connect("api1")
        health = runtime.health_check()
        assert health.connected_count == 1

    def test_custom_settings(self) -> None:
        """Test runtime with custom settings."""
        settings = Settings(
            service_name="custom-integrations",
            default_timeout_seconds=60,
            default_retry_count=5,
        )
        runtime = IntegrationsRuntime(settings=settings)

        assert runtime.settings.default_timeout_seconds == 60
        assert runtime.settings.default_retry_count == 5
