"""Unified in-memory telemetry backend for testing."""

from __future__ import annotations

import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any

from factory.telemetry.runtime.ports import (
    MetricValue,
    SpanData,
    LogEntry,
    Severity,
)
from factory.telemetry.runtime.adapters.memory import (
    MemoryMetricsExporter,
    MemoryTraceExporter,
    MemoryLogExporter,
)


class MemoryTelemetryBackend:
    """Unified in-memory telemetry backend for testing.
    
    Implements the TelemetryBackend protocol with in-memory storage.
    """
    
    def __init__(self, max_size: int = 1000) -> None:
        self._metrics_exporter = MemoryMetricsExporter(max_size=max_size)
        self._trace_exporter = MemoryTraceExporter(max_size=max_size)
        self._log_exporter = MemoryLogExporter()
        self._active_spans: dict[str, SpanData] = {}
        self._current_trace_id: str = uuid.uuid4().hex
    
    def record_metric(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record a metric value with optional labels."""
        metric = MetricValue(name=name, value=value, labels=labels or {})
        self._metrics_exporter.export_metric(metric)
    
    def start_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> SpanData:
        """Start a new span and return its data."""
        span = SpanData(
            trace_id=self._current_trace_id,
            span_id=uuid.uuid4().hex[:16],
            name=name,
            start_time=datetime.now(timezone.utc).timestamp(),
            attributes=attributes or {},
        )
        self._active_spans[span.span_id] = span
        return span
    
    def end_span(self, span: SpanData, error: str | None = None) -> None:
        """End a span, optionally recording an error."""
        span.end_time = datetime.now(timezone.utc).timestamp()
        if error:
            span.status = "ERROR"
            span.error_message = error
        self._active_spans.pop(span.span_id, None)
        self._trace_exporter.export_span(span)
    
    def record_log(
        self,
        severity: Severity,
        body: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Record a log entry."""
        entry = LogEntry(
            severity=severity,
            body=body,
            attributes=attributes or {},
            trace_id=self._current_trace_id,
        )
        self._log_exporter.export_log(entry)
    
    def flush(self) -> None:
        """Flush all exporters (no-op for memory)."""
        self._metrics_exporter.flush()
        self._trace_exporter.flush()
        self._log_exporter.flush()
    
    def health_check(self) -> dict[str, Any]:
        """Return health status with counts."""
        return {
            "ok": True,
            "backend": "memory",
            "metrics_count": len(self._metrics_exporter.metrics),
            "spans_count": len(self._trace_exporter.spans),
            "logs_count": len(self._log_exporter.logs),
            "active_spans": len(self._active_spans),
        }
    
    # Test helpers
    @property
    def metrics(self) -> list[MetricValue]:
        """Access stored metrics for assertions."""
        return self._metrics_exporter.metrics
    
    @property
    def spans(self) -> list[SpanData]:
        """Access stored spans for assertions."""
        return self._trace_exporter.spans
    
    @property
    def logs(self) -> deque[LogEntry]:
        """Access stored logs for assertions."""
        return self._log_exporter.logs
    
    def clear(self) -> None:
        """Clear all stored telemetry data."""
        self._metrics_exporter.clear()
        self._trace_exporter.clear()
        self._log_exporter.clear()
        self._active_spans.clear()
