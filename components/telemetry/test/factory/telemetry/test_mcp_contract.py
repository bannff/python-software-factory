"""Tests for MCP contract compliance (Brick MCP Contract).

Every MCP-enabled brick MUST expose:
- get_capabilities() - Machine-readable feature list
- health_check() - Fast readiness probe
- describe_config_schema() - JSON schema for configuration
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from factory.telemetry.runtime.runtime import TelemetryRuntime


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Create a minimal config directory for testing."""
    cfg = tmp_path / "config"
    (cfg / "metrics").mkdir(parents=True)
    (cfg / "exporters").mkdir(parents=True)
    (cfg / "settings.yaml").write_text(
        """
service:
  name: test-service
otel:
  enabled: true
  tracing_enabled: false
  metrics_enabled: false
  logging_enabled: false
authoring:
  enabled: false
""".lstrip()
    )
    return cfg


@pytest.fixture
def runtime(config_dir: Path) -> TelemetryRuntime:
    """Create an initialized TelemetryRuntime."""
    eng = TelemetryRuntime(config_dir=config_dir)
    eng.initialize()
    return eng


class TestGetCapabilities:
    """Tests for get_capabilities MCP contract method."""

    def test_returns_dict(self, runtime: TelemetryRuntime) -> None:
        """get_capabilities must return a dictionary."""
        result = runtime.get_capabilities()
        assert isinstance(result, dict)

    def test_has_module_name(self, runtime: TelemetryRuntime) -> None:
        """Capabilities must include module name."""
        result = runtime.get_capabilities()
        assert "module" in result
        assert result["module"] == "telemetry-module"

    def test_has_version(self, runtime: TelemetryRuntime) -> None:
        """Capabilities must include version."""
        result = runtime.get_capabilities()
        assert "version" in result
        assert isinstance(result["version"], str)

    def test_has_deterministic_tools(self, runtime: TelemetryRuntime) -> None:
        """Capabilities must list deterministic tools."""
        result = runtime.get_capabilities()
        assert "deterministic_tools" in result
        tools = result["deterministic_tools"]
        assert isinstance(tools, list)
        assert "get_capabilities" in tools
        assert "health_check" in tools
        assert "describe_config_schema" in tools

    def test_has_recording_tools(self, runtime: TelemetryRuntime) -> None:
        """Capabilities must list recording tools."""
        result = runtime.get_capabilities()
        assert "recording_tools" in result
        tools = result["recording_tools"]
        assert "record_llm_interaction" in tools
        assert "record_agent_execution" in tools
        assert "record_tool_invocation" in tools

    def test_has_authoring_info(self, runtime: TelemetryRuntime) -> None:
        """Capabilities must include authoring configuration."""
        result = runtime.get_capabilities()
        assert "authoring" in result
        assert "env_var" in result["authoring"]


class TestHealthCheck:
    """Tests for health_check MCP contract method."""

    def test_returns_dict(self, runtime: TelemetryRuntime) -> None:
        """health_check must return a dictionary."""
        result = runtime.health_check()
        assert isinstance(result, dict)

    def test_has_ok_status(self, runtime: TelemetryRuntime) -> None:
        """health_check must include ok status."""
        result = runtime.health_check()
        assert "ok" in result
        assert result["ok"] is True

    def test_has_service_info(self, runtime: TelemetryRuntime) -> None:
        """health_check must include service information."""
        result = runtime.health_check()
        assert "service" in result
        assert "name" in result["service"]

    def test_has_otel_status(self, runtime: TelemetryRuntime) -> None:
        """health_check must include OpenTelemetry status."""
        result = runtime.health_check()
        assert "otel" in result
        otel = result["otel"]
        assert "enabled" in otel
        assert "tracing_enabled" in otel
        assert "metrics_enabled" in otel

    def test_has_exporters_list(self, runtime: TelemetryRuntime) -> None:
        """health_check must list configured exporters."""
        result = runtime.health_check()
        assert "exporters" in result
        assert isinstance(result["exporters"], list)


class TestDescribeConfigSchema:
    """Tests for describe_config_schema MCP contract method."""

    def test_returns_dict(self, runtime: TelemetryRuntime) -> None:
        """describe_config_schema must return a dictionary."""
        result = runtime.describe_config_schema()
        assert isinstance(result, dict)

    def test_has_schema_version(self, runtime: TelemetryRuntime) -> None:
        """Schema must include version."""
        result = runtime.describe_config_schema()
        assert "schema_version" in result

    def test_has_schemas_section(self, runtime: TelemetryRuntime) -> None:
        """Schema must include schemas section."""
        result = runtime.describe_config_schema()
        assert "schemas" in result
        schemas = result["schemas"]
        assert isinstance(schemas, dict)

    def test_has_settings_schema(self, runtime: TelemetryRuntime) -> None:
        """Schema must include settings schema."""
        result = runtime.describe_config_schema()
        schemas = result["schemas"]
        assert "settings" in schemas
        assert isinstance(schemas["settings"], dict)

    def test_has_exporter_schema(self, runtime: TelemetryRuntime) -> None:
        """Schema must include exporter schema."""
        result = runtime.describe_config_schema()
        schemas = result["schemas"]
        assert "exporter" in schemas

    def test_has_metric_definition_schema(self, runtime: TelemetryRuntime) -> None:
        """Schema must include metric definition schema."""
        result = runtime.describe_config_schema()
        schemas = result["schemas"]
        assert "metric_definition" in schemas
