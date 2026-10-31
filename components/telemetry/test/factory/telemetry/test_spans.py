"""Tests for span lifecycle and log recording."""

from __future__ import annotations

from pathlib import Path

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
    runtime_instance = TelemetryRuntime(config_dir=config_dir)
    runtime_instance.initialize()
    return runtime_instance


class TestSpanLifecycle:
    """Tests for span start/end lifecycle."""

    def test_start_span(self, runtime: TelemetryRuntime) -> None:
        """Test starting a span."""
        result = runtime.start_span("test.operation", {"key": "value"})
        
        assert result["ok"] is True
        assert "span_id" in result
        assert result["span_id"] is not None

    def test_end_span(self, runtime: TelemetryRuntime) -> None:
        """Test ending a span."""
        start_result = runtime.start_span("test.operation", None)
        span_id = start_result["span_id"]
        
        end_result = runtime.end_span(span_id, error=None)
        
        assert end_result["ok"] is True
        assert end_result["span_id"] == span_id

    def test_end_span_with_error(self, runtime: TelemetryRuntime) -> None:
        """Test ending a span with an error."""
        start_result = runtime.start_span("failing.operation", None)
        span_id = start_result["span_id"]
        
        end_result = runtime.end_span(span_id, error="Something failed")
        
        assert end_result["ok"] is True
        snap = runtime.metrics_snapshot()
        assert snap["errors"] == 1

    def test_end_nonexistent_span(self, runtime: TelemetryRuntime) -> None:
        """Test ending a span that doesn't exist."""
        result = runtime.end_span("nonexistent-span-id", error=None)
        
        assert result["ok"] is False
        assert result["error"] == "span_not_found"

    def test_multiple_concurrent_spans(self, runtime: TelemetryRuntime) -> None:
        """Test managing multiple concurrent spans."""
        span1 = runtime.start_span("operation.1", None)
        span2 = runtime.start_span("operation.2", None)
        span3 = runtime.start_span("operation.3", None)
        
        # End in different order
        runtime.end_span(span2["span_id"], None)
        runtime.end_span(span1["span_id"], None)
        runtime.end_span(span3["span_id"], None)
        
        # All should succeed
        assert len(runtime.state.spans) == 0


class TestRecordLog:
    """Tests for record_log functionality."""

    def test_record_info_log(self, runtime: TelemetryRuntime) -> None:
        """Test recording an INFO log."""
        result = runtime.record_log(
            severity="INFO",
            body="Test log message",
            attributes={"key": "value"},
        )
        
        assert result["ok"] is True
        assert result["recorded"] == "log"

    def test_updates_log_snapshot(self, runtime: TelemetryRuntime) -> None:
        """Test that recording updates log snapshot."""
        runtime.record_log(severity="INFO", body="Info message", attributes=None)
        runtime.record_log(severity="ERROR", body="Error message", attributes=None)
        runtime.record_log(severity="INFO", body="Another info", attributes=None)
        
        snap = runtime.metrics_snapshot()
        assert snap["logs"]["total"] == 3
        assert snap["logs"]["by_severity"]["INFO"] == 2
        assert snap["logs"]["by_severity"]["ERROR"] == 1

    def test_warning_severity_normalized(self, runtime: TelemetryRuntime) -> None:
        """Test that WARNING is normalized to WARN."""
        runtime.record_log(severity="WARNING", body="Warning message", attributes=None)
        
        snap = runtime.metrics_snapshot()
        assert snap["logs"]["by_severity"].get("WARN", 0) == 1
