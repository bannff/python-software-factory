"""Tests for UI MCP contract tools.

Verifies that the UI brick exposes the required contract tools:
- get_capabilities
- health_check
- describe_config_schema
"""

import pytest

from factory.ui.runtime.runtime import UIRuntime, reset_runtime


class TestMCPContract:
    """Tests for MCP contract compliance."""

    @pytest.fixture(autouse=True)
    def reset(self) -> None:
        """Reset global runtime before each test."""
        reset_runtime()

    def test_get_capabilities_returns_required_fields(self) -> None:
        """get_capabilities should return module info and features."""
        runtime = UIRuntime()
        runtime.initialize()

        caps = runtime.get_capabilities()

        assert "module" in caps
        assert caps["module"] == "ui-module"
        assert "version" in caps
        assert "schema_version" in caps
        assert "adapters" in caps
        assert "component_types" in caps

    def test_get_capabilities_lists_adapters(self) -> None:
        """get_capabilities should list available adapters."""
        runtime = UIRuntime()
        runtime.initialize()

        caps = runtime.get_capabilities()

        assert "adapters" in caps
        # Adapters is a dict with 'available' containing list of adapter metadata dicts
        assert "available" in caps["adapters"]
        available = caps["adapters"]["available"]
        # Each adapter is a dict with 'type', 'content_type', 'streaming'
        adapter_types = [a["type"] for a in available]
        assert "json" in adapter_types
        assert "a2ui-htmx" in adapter_types
        assert "a2ui-react" in adapter_types

    def test_get_capabilities_lists_component_types(self) -> None:
        """get_capabilities should list available component types."""
        runtime = UIRuntime()
        runtime.initialize()

        caps = runtime.get_capabilities()

        assert isinstance(caps["component_types"], list)
        assert len(caps["component_types"]) > 0

    def test_health_check_returns_status(self) -> None:
        """health_check should return status field."""
        runtime = UIRuntime()
        runtime.initialize()

        health = runtime.health_check()

        assert "status" in health
        assert health["status"] in ("healthy", "unhealthy")

    def test_health_check_returns_checks(self) -> None:
        """health_check should return individual checks."""
        runtime = UIRuntime()
        runtime.initialize()

        health = runtime.health_check()

        assert "checks" in health
        assert "initialized" in health["checks"]
        assert "store" in health["checks"]

    def test_health_check_not_initialized(self) -> None:
        """health_check should report unhealthy when not initialized."""
        runtime = UIRuntime()
        # Don't initialize

        health = runtime.health_check()

        # Can be "unhealthy", "not_initialized", or status key may not exist
        status = health.get("status", "not_initialized")
        assert status in ("unhealthy", "not_initialized")

    def test_describe_config_schema_returns_json_schema(self) -> None:
        """describe_config_schema should return valid JSON schema."""
        runtime = UIRuntime()

        schema = runtime.describe_config_schema()

        assert "$schema" in schema
        assert "properties" in schema

    def test_describe_config_schema_has_settings(self) -> None:
        """describe_config_schema should include settings definition."""
        runtime = UIRuntime()

        schema = runtime.describe_config_schema()

        assert "settings" in schema["properties"]

    def test_describe_config_schema_has_view_definition(self) -> None:
        """describe_config_schema should include view definition."""
        runtime = UIRuntime()

        schema = runtime.describe_config_schema()

        assert "view_definition" in schema["properties"]
