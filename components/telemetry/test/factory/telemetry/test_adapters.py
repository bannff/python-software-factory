"""Tests for telemetry adapters (memory exporters)."""

from __future__ import annotations

import pytest

from factory.telemetry.runtime.ports import MetricValue, SpanData, LogEntry, Severity
from factory.telemetry.runtime.adapters.memory import (
    MemoryMetricsExporter,
    MemoryTraceExporter,
    MemoryLogExporter,
)


class TestMemoryMetricsExporter:
    """Tests for MemoryMetricsExporter adapter."""

    @pytest.fixture
    def exporter(self) -> MemoryMetricsExporter:
        """Create a memory metrics exporter."""
        return MemoryMetricsExporter()

    def test_export_metric(self, exporter: MemoryMetricsExporter) -> None:
        """Test exporting a single metric."""
        metric = MetricValue(name="test.counter", value=42.0)
        result = exporter.export_metric(metric)
        
        assert result is True
        assert len(exporter.metrics) == 1
        assert exporter.metrics[0].name == "test.counter"

    def test_export_batch(self, exporter: MemoryMetricsExporter) -> None:
        """Test exporting a batch of metrics."""
        metrics = [
            MetricValue(name="metric.a", value=1.0),
            MetricValue(name="metric.b", value=2.0),
        ]
        result = exporter.export_batch(metrics)
        
        assert result is True
        assert len(exporter.metrics) == 2

    def test_max_size_eviction(self) -> None:
        """Test that old metrics are evicted when max size reached."""
        exporter = MemoryMetricsExporter(max_size=2)
        exporter.export_metric(MetricValue(name="first", value=1.0))
        exporter.export_metric(MetricValue(name="second", value=2.0))
        exporter.export_metric(MetricValue(name="third", value=3.0))
        
        assert len(exporter.metrics) == 2
        assert exporter.metrics[0].name == "second"
        assert exporter.metrics[1].name == "third"

    def test_get_by_name(self, exporter: MemoryMetricsExporter) -> None:
        """Test filtering metrics by name."""
        exporter.export_metric(MetricValue(name="llm.tokens", value=100.0))
        exporter.export_metric(MetricValue(name="agent.exec", value=1.0))
        exporter.export_metric(MetricValue(name="llm.tokens", value=200.0))
        
        llm_metrics = exporter.get_by_name("llm.tokens")
        assert len(llm_metrics) == 2

    def test_clear(self, exporter: MemoryMetricsExporter) -> None:
        """Test clearing all metrics."""
        exporter.export_metric(MetricValue(name="test", value=1.0))
        exporter.clear()
        
        assert len(exporter.metrics) == 0

    def test_flush_noop(self, exporter: MemoryMetricsExporter) -> None:
        """Test that flush is a no-op for memory exporter."""
        exporter.export_metric(MetricValue(name="test", value=1.0))
        exporter.flush()  # Should not raise
        assert len(exporter.metrics) == 1


class TestMemoryTraceExporter:
    """Tests for MemoryTraceExporter adapter."""

    @pytest.fixture
    def exporter(self) -> MemoryTraceExporter:
        """Create a memory trace exporter."""
        return MemoryTraceExporter()

    def test_export_span(self, exporter: MemoryTraceExporter) -> None:
        """Test exporting a single span."""
        span = SpanData(
            trace_id="abc123",
            span_id="span1",
            name="test.operation",
            start_time=1000.0,
        )
        result = exporter.export_span(span)
        
        assert result is True
        assert len(exporter.spans) == 1

    def test_get_by_trace_id(self, exporter: MemoryTraceExporter) -> None:
        """Test filtering spans by trace ID."""
        exporter.export_span(SpanData(
            trace_id="trace1", span_id="s1", name="op1", start_time=1.0
        ))
        exporter.export_span(SpanData(
            trace_id="trace2", span_id="s2", name="op2", start_time=2.0
        ))
        exporter.export_span(SpanData(
            trace_id="trace1", span_id="s3", name="op3", start_time=3.0
        ))
        
        trace1_spans = exporter.get_by_trace_id("trace1")
        assert len(trace1_spans) == 2

    def test_get_by_name(self, exporter: MemoryTraceExporter) -> None:
        """Test filtering spans by name."""
        exporter.export_span(SpanData(
            trace_id="t1", span_id="s1", name="llm.call", start_time=1.0
        ))
        exporter.export_span(SpanData(
            trace_id="t1", span_id="s2", name="tool.invoke", start_time=2.0
        ))
        
        llm_spans = exporter.get_by_name("llm.call")
        assert len(llm_spans) == 1


class TestMemoryLogExporter:
    """Tests for MemoryLogExporter adapter."""

    @pytest.fixture
    def exporter(self) -> MemoryLogExporter:
        """Create a memory log exporter."""
        return MemoryLogExporter()

    def test_export_log(self, exporter: MemoryLogExporter) -> None:
        """Test exporting a single log entry."""
        entry = LogEntry(severity=Severity.INFO, body="Test message")
        result = exporter.export_log(entry)
        
        assert result is True
        assert len(exporter.logs) == 1

    def test_get_by_severity(self, exporter: MemoryLogExporter) -> None:
        """Test filtering logs by severity."""
        exporter.export_log(LogEntry(severity=Severity.INFO, body="Info"))
        exporter.export_log(LogEntry(severity=Severity.ERROR, body="Error"))
        exporter.export_log(LogEntry(severity=Severity.INFO, body="Info 2"))
        
        info_logs = exporter.get_by_severity(Severity.INFO)
        assert len(info_logs) == 2

    def test_tail(self, exporter: MemoryLogExporter) -> None:
        """Test getting last N log entries."""
        for i in range(10):
            exporter.export_log(LogEntry(severity=Severity.INFO, body=f"Log {i}"))
        
        last_3 = exporter.tail(3)
        assert len(last_3) == 3
        assert last_3[-1].body == "Log 9"
