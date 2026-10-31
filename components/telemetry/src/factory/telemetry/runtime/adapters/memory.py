"""In-memory telemetry adapters for testing.

These adapters store telemetry data in memory, making them ideal for:
- Unit tests that need to verify telemetry was recorded
- Integration tests without external dependencies
- Development/debugging scenarios
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from factory.telemetry.runtime.ports import (
    MetricValue,
    SpanData,
    LogEntry,
    Severity,
)


@dataclass
class MemoryMetricsExporter:
    """In-memory metrics exporter for testing."""
    
    metrics: list[MetricValue] = field(default_factory=list)
    max_size: int = 1000
    
    def export_metric(self, metric: MetricValue) -> bool:
        """Store metric in memory."""
        if len(self.metrics) >= self.max_size:
            self.metrics.pop(0)
        self.metrics.append(metric)
        return True
    
    def export_batch(self, metrics: list[MetricValue]) -> bool:
        """Store batch of metrics in memory."""
        for metric in metrics:
            self.export_metric(metric)
        return True
    
    def flush(self) -> None:
        """No-op for in-memory storage."""
        pass
    
    def clear(self) -> None:
        """Clear all stored metrics."""
        self.metrics.clear()
    
    def get_by_name(self, name: str) -> list[MetricValue]:
        """Get all metrics with a specific name."""
        return [m for m in self.metrics if m.name == name]


@dataclass
class MemoryTraceExporter:
    """In-memory trace exporter for testing."""
    
    spans: list[SpanData] = field(default_factory=list)
    max_size: int = 1000
    
    def export_span(self, span: SpanData) -> bool:
        """Store span in memory."""
        if len(self.spans) >= self.max_size:
            self.spans.pop(0)
        self.spans.append(span)
        return True
    
    def export_batch(self, spans: list[SpanData]) -> bool:
        """Store batch of spans in memory."""
        for span in spans:
            self.export_span(span)
        return True
    
    def flush(self) -> None:
        """No-op for in-memory storage."""
        pass
    
    def clear(self) -> None:
        """Clear all stored spans."""
        self.spans.clear()
    
    def get_by_trace_id(self, trace_id: str) -> list[SpanData]:
        """Get all spans for a specific trace."""
        return [s for s in self.spans if s.trace_id == trace_id]
    
    def get_by_name(self, name: str) -> list[SpanData]:
        """Get all spans with a specific name."""
        return [s for s in self.spans if s.name == name]


@dataclass
class MemoryLogExporter:
    """In-memory log exporter for testing."""
    
    logs: deque[LogEntry] = field(default_factory=lambda: deque(maxlen=1000))
    
    def export_log(self, entry: LogEntry) -> bool:
        """Store log entry in memory."""
        self.logs.append(entry)
        return True
    
    def export_batch(self, entries: list[LogEntry]) -> bool:
        """Store batch of log entries in memory."""
        for entry in entries:
            self.export_log(entry)
        return True
    
    def flush(self) -> None:
        """No-op for in-memory storage."""
        pass
    
    def clear(self) -> None:
        """Clear all stored logs."""
        self.logs.clear()
    
    def get_by_severity(self, severity: Severity) -> list[LogEntry]:
        """Get all logs with a specific severity."""
        return [log for log in self.logs if log.severity == severity]
    
    def tail(self, n: int = 20) -> list[LogEntry]:
        """Get the last n log entries."""
        return list(self.logs)[-n:]
