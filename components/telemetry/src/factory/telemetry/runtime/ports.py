"""Abstract ports for telemetry brick.

Ports define what capabilities the telemetry system needs, not how they're implemented.
Adapters plug in specific backends (OpenTelemetry, in-memory, CloudWatch, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class Severity(Enum):
    """Standard log severity levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


@dataclass
class MetricValue:
    """A single metric data point - framework-agnostic representation."""
    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    
    # Optional metadata
    unit: str | None = None
    description: str | None = None


@dataclass
class SpanData:
    """A single trace span - framework-agnostic representation."""
    trace_id: str
    span_id: str
    name: str
    start_time: float
    end_time: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    
    # Optional metadata
    parent_span_id: str | None = None
    status: str = "OK"  # OK, ERROR
    error_message: str | None = None


@dataclass
class LogEntry:
    """A single log entry - framework-agnostic representation."""
    severity: Severity
    body: str
    timestamp: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    attributes: dict[str, Any] = field(default_factory=dict)
    
    # Optional trace correlation
    trace_id: str | None = None
    span_id: str | None = None


@runtime_checkable
class MetricsExporter(Protocol):
    """Port: Where metrics are exported (OTLP, Prometheus, CloudWatch, etc.)"""
    
    def export_metric(self, metric: MetricValue) -> bool:
        """Export a single metric value. Returns True on success."""
        ...
    
    def export_batch(self, metrics: list[MetricValue]) -> bool:
        """Export a batch of metrics. Returns True on success."""
        ...
    
    def flush(self) -> None:
        """Flush any buffered metrics."""
        ...


@runtime_checkable
class TraceExporter(Protocol):
    """Port: Where trace spans are exported (OTLP, Jaeger, Zipkin, etc.)"""
    
    def export_span(self, span: SpanData) -> bool:
        """Export a single span. Returns True on success."""
        ...
    
    def export_batch(self, spans: list[SpanData]) -> bool:
        """Export a batch of spans. Returns True on success."""
        ...
    
    def flush(self) -> None:
        """Flush any buffered spans."""
        ...


@runtime_checkable
class LogExporter(Protocol):
    """Port: Where logs are exported (OTLP, CloudWatch, file, etc.)"""
    
    def export_log(self, entry: LogEntry) -> bool:
        """Export a single log entry. Returns True on success."""
        ...
    
    def export_batch(self, entries: list[LogEntry]) -> bool:
        """Export a batch of log entries. Returns True on success."""
        ...
    
    def flush(self) -> None:
        """Flush any buffered logs."""
        ...


@runtime_checkable
class TelemetryBackend(Protocol):
    """Port: Unified telemetry backend combining metrics, traces, and logs."""
    
    # Metrics
    def record_metric(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record a metric value with optional labels."""
        ...
    
    # Tracing
    def start_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> SpanData:
        """Start a new span and return its data."""
        ...
    
    def end_span(self, span: SpanData, error: str | None = None) -> None:
        """End a span, optionally recording an error."""
        ...
    
    # Logging
    def record_log(
        self,
        severity: Severity,
        body: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Record a log entry."""
        ...
    
    # Lifecycle
    def flush(self) -> None:
        """Flush all buffered telemetry data."""
        ...
    
    def health_check(self) -> dict[str, Any]:
        """Check backend health/status."""
        ...


@runtime_checkable
class SpanCapture(Protocol):
    """Port: In-memory span capture for evals/agent telemetry."""

    def setup(self) -> "SpanCapture": ...
    def clear(self) -> None: ...
    def get_finished_spans(self) -> list[Any]: ...
    def spans_to_session(self, spans: list[Any], session_id: str = "unknown") -> Any: ...

    @property
    def ready(self) -> bool: ...
