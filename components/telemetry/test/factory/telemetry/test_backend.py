"""Tests for unified MemoryTelemetryBackend."""

from __future__ import annotations

import pytest

from factory.telemetry.runtime.ports import Severity
from factory.telemetry.runtime.adapters.backend import MemoryTelemetryBackend


class TestMemoryTelemetryBackend:
    """Tests for unified MemoryTelemetryBackend."""

    @pytest.fixture
    def backend(self) -> MemoryTelemetryBackend:
        """Create a memory telemetry backend."""
        return MemoryTelemetryBackend()

    def test_record_metric(self, backend: MemoryTelemetryBackend) -> None:
        """Test recording a metric."""
        backend.record_metric("test.counter", 42.0, {"env": "test"})
        
        assert len(backend.metrics) == 1
        assert backend.metrics[0].name == "test.counter"
        assert backend.metrics[0].value == 42.0

    def test_span_lifecycle(self, backend: MemoryTelemetryBackend) -> None:
        """Test starting and ending a span."""
        span = backend.start_span("test.operation", {"key": "value"})
        
        assert span.name == "test.operation"
        assert span.trace_id is not None
        assert span.span_id is not None
        
        backend.end_span(span)
        
        assert len(backend.spans) == 1
        assert backend.spans[0].end_time is not None

    def test_span_with_error(self, backend: MemoryTelemetryBackend) -> None:
        """Test ending a span with an error."""
        span = backend.start_span("failing.operation")
        backend.end_span(span, error="Something went wrong")
        
        assert backend.spans[0].status == "ERROR"
        assert backend.spans[0].error_message == "Something went wrong"

    def test_record_log(self, backend: MemoryTelemetryBackend) -> None:
        """Test recording a log entry."""
        backend.record_log(Severity.WARN, "Warning message", {"context": "test"})
        
        assert len(backend.logs) == 1
        assert backend.logs[0].severity == Severity.WARN

    def test_health_check(self, backend: MemoryTelemetryBackend) -> None:
        """Test health check returns status."""
        backend.record_metric("m1", 1.0)
        backend.record_log(Severity.INFO, "test")
        
        health = backend.health_check()
        
        assert health["ok"] is True
        assert health["backend"] == "memory"
        assert health["metrics_count"] == 1
        assert health["logs_count"] == 1

    def test_clear(self, backend: MemoryTelemetryBackend) -> None:
        """Test clearing all telemetry data."""
        backend.record_metric("m1", 1.0)
        backend.record_log(Severity.INFO, "test")
        backend.clear()
        
        assert len(backend.metrics) == 0
        assert len(backend.logs) == 0

    def test_flush_noop(self, backend: MemoryTelemetryBackend) -> None:
        """Test that flush is a no-op for memory backend."""
        backend.record_metric("m1", 1.0)
        backend.flush()  # Should not raise
        assert len(backend.metrics) == 1
