"""Tests for TelemetryRuntime runtime factory and backend selection."""

from __future__ import annotations

from pathlib import Path

import pytest

from factory.telemetry.runtime.runtime import TelemetryRuntime, TelemetryState
from factory.telemetry.runtime.metrics import MetricsSnapshot


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
  version: "1.0.0"
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
def otel_enabled_config(tmp_path: Path) -> Path:
    """Create config with OTel tracing enabled."""
    cfg = tmp_path / "otel_config"
    (cfg / "metrics").mkdir(parents=True)
    (cfg / "exporters").mkdir(parents=True)
    (cfg / "settings.yaml").write_text(
        """
service:
  name: otel-test-service
otel:
  enabled: true
  tracing_enabled: true
  metrics_enabled: true
  logging_enabled: false
""".lstrip()
    )
    return cfg


class TestTelemetryRuntimeFactory:
    """Tests for TelemetryRuntime instantiation and initialization."""

    def test_create_runtime(self, config_dir: Path) -> None:
        """Test creating a TelemetryRuntime instance."""
        runtime = TelemetryRuntime(config_dir=config_dir)
        assert runtime.config_dir == config_dir
        assert runtime.settings is None  # Not initialized yet

    def test_initialize_loads_settings(self, config_dir: Path) -> None:
        """Test that initialize() loads settings."""
        runtime = TelemetryRuntime(config_dir=config_dir)
        runtime.initialize()
        
        assert runtime.settings is not None
        assert runtime.settings.service.name == "test-service"

    def test_initialize_creates_tracer(self, config_dir: Path) -> None:
        """Test that initialize() creates a tracer."""
        runtime = TelemetryRuntime(config_dir=config_dir)
        runtime.initialize()
        
        assert runtime._tracer is not None

    def test_initialize_creates_meter(self, config_dir: Path) -> None:
        """Test that initialize() creates a meter."""
        runtime = TelemetryRuntime(config_dir=config_dir)
        runtime.initialize()
        
        assert runtime._meter is not None

    def test_initialize_creates_instruments(self, config_dir: Path) -> None:
        """Test that initialize() creates OTel instruments."""
        runtime = TelemetryRuntime(config_dir=config_dir)
        runtime.initialize()
        
        assert runtime._instruments is not None
        assert isinstance(runtime._instruments, dict)

    def test_state_initialized(self, config_dir: Path) -> None:
        """Test that runtime state is properly initialized."""
        runtime = TelemetryRuntime(config_dir=config_dir)
        
        assert isinstance(runtime.state, TelemetryState)
        assert isinstance(runtime.state.snapshot, MetricsSnapshot)
        assert runtime.state.spans == {}


class TestTelemetryRuntimeConfiguration:
    """Tests for TelemetryRuntime configuration handling."""

    def test_settings_raw_available(self, config_dir: Path) -> None:
        """Test that raw settings dict is available after init."""
        runtime = TelemetryRuntime(config_dir=config_dir)
        runtime.initialize()
        
        assert runtime.settings_raw is not None
        assert isinstance(runtime.settings_raw, dict)
        assert "service" in runtime.settings_raw

    def test_registries_loaded(self, config_dir: Path) -> None:
        """Test that registries are loaded."""
        runtime = TelemetryRuntime(config_dir=config_dir)
        
        assert runtime.registries is not None
        assert runtime.registries.metrics is not None
        assert runtime.registries.exporters is not None

    def test_otel_runtime_created(self, config_dir: Path) -> None:
        """Test that OTel runtime is created after init."""
        runtime = TelemetryRuntime(config_dir=config_dir)
        runtime.initialize()
        
        assert runtime.otel is not None


class TestTelemetryRuntimeInstruments:
    """Tests for TelemetryRuntime instrument accessors."""

    def test_counter_llm_tokens_accessor(self, config_dir: Path) -> None:
        """Test _counter_llm_tokens property."""
        runtime = TelemetryRuntime(config_dir=config_dir)
        runtime.initialize()
        
        # Accessor should return instrument or None
        counter = runtime._counter_llm_tokens
        # May be None if not configured, but accessor should work
        assert counter is None or hasattr(counter, "add")

    def test_hist_llm_latency_accessor(self, config_dir: Path) -> None:
        """Test _hist_llm_latency_ms property."""
        runtime = TelemetryRuntime(config_dir=config_dir)
        runtime.initialize()
        
        hist = runtime._hist_llm_latency_ms
        assert hist is None or hasattr(hist, "record")

    def test_counter_agent_exec_accessor(self, config_dir: Path) -> None:
        """Test _counter_agent_exec property."""
        runtime = TelemetryRuntime(config_dir=config_dir)
        runtime.initialize()
        
        counter = runtime._counter_agent_exec
        assert counter is None or hasattr(counter, "add")

    def test_counter_tool_invocations_accessor(self, config_dir: Path) -> None:
        """Test _counter_tool_invocations property."""
        runtime = TelemetryRuntime(config_dir=config_dir)
        runtime.initialize()
        
        counter = runtime._counter_tool_invocations
        assert counter is None or hasattr(counter, "add")


class TestTelemetryRuntimeContextPropagation:
    """Tests for context propagation methods."""

    def test_inject_context(self, config_dir: Path) -> None:
        """Test inject_context returns carrier dict."""
        runtime = TelemetryRuntime(config_dir=config_dir)
        runtime.initialize()
        
        result = runtime.inject_context()
        assert result["ok"] is False
        assert result["outcome"] == "no_context"
        assert "carrier" in result

    def test_extract_context_empty_carrier(self, config_dir: Path) -> None:
        """Test extract_context with empty carrier."""
        runtime = TelemetryRuntime(config_dir=config_dir)
        runtime.initialize()
        
        result = runtime.extract_context({})
        assert result["ok"] is False
        assert result["outcome"] == "rejected"
        assert result["error"] == "missing traceparent"
