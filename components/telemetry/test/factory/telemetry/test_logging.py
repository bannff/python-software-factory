"""Tests for logging functionality."""
from __future__ import annotations

from pathlib import Path

from factory.telemetry.runtime.runtime import TelemetryRuntime


def _create_runtime(tmp_path: Path, logging_enabled: bool = True) -> TelemetryRuntime:
    """Create a test runtime with logging config."""
    cfg = tmp_path / "config"
    (cfg / "metrics").mkdir(parents=True)
    (cfg / "exporters").mkdir(parents=True)
    (cfg / "settings.yaml").write_text(
        f"""
service:
  name: test-service
otel:
  enabled: true
  tracing_enabled: false
  metrics_enabled: false
  logging_enabled: {str(logging_enabled).lower()}
""".lstrip()
    )
    runtime = TelemetryRuntime(config_dir=cfg)
    runtime.initialize()
    return runtime


class TestRecordLog:
    """Test log recording functionality."""

    def test_record_log_info(self, tmp_path: Path) -> None:
        """Should record INFO level log."""
        runtime = _create_runtime(tmp_path)
        
        result = runtime.record_log(
            severity="INFO",
            body="Test log message",
            attributes={"key": "value"},
        )
        
        assert result["ok"] is True
        assert result["recorded"] == "log"

    def test_record_log_error(self, tmp_path: Path) -> None:
        """Should record ERROR level log."""
        runtime = _create_runtime(tmp_path)
        
        result = runtime.record_log(
            severity="ERROR",
            body="Error occurred",
            attributes={"error_code": "E001"},
        )
        
        assert result["ok"] is True

    def test_record_log_with_trace_context(self, tmp_path: Path) -> None:
        """Should record log with trace context."""
        runtime = _create_runtime(tmp_path)
        
        result = runtime.record_log(
            severity="DEBUG",
            body="Debug message",
            attributes=None,
            trace_id="abc123",
            span_id="def456",
        )
        
        assert result["ok"] is True

    def test_record_log_updates_snapshot(self, tmp_path: Path) -> None:
        """Log recording should update metrics snapshot."""
        runtime = _create_runtime(tmp_path)
        
        runtime.record_log(severity="INFO", body="msg1", attributes=None)
        runtime.record_log(severity="ERROR", body="msg2", attributes=None)
        
        snap = runtime.metrics_snapshot()
        assert snap["logs"]["total"] == 2
        assert snap["logs"]["by_severity"]["ERROR"] == 1

    def test_all_severity_levels(self, tmp_path: Path) -> None:
        """Should support all standard severity levels."""
        runtime = _create_runtime(tmp_path)
        
        for severity in ["DEBUG", "INFO", "WARN", "ERROR"]:
            result = runtime.record_log(
                severity=severity,
                body=f"{severity} message",
                attributes=None,
            )
            assert result["ok"] is True
