"""Tests for AWS CloudWatch + X-Ray telemetry adapter."""

import pytest
from unittest.mock import MagicMock, patch

from factory.telemetry.runtime.ports import Severity, SpanData


@pytest.fixture
def mock_boto3():
    with patch("boto3.client") as mc:
        mc.return_value = MagicMock()
        yield mc


@pytest.fixture
def backend(mock_boto3):
    from factory.telemetry.runtime.adapters.aws import AWSCloudWatchBackend

    b = AWSCloudWatchBackend(namespace="TestNS", log_group="/test/logs")
    return b


def test_invalid_namespace(mock_boto3):
    from factory.telemetry.runtime.adapters.aws import AWSCloudWatchBackend

    with pytest.raises(ValueError, match="Invalid namespace"):
        AWSCloudWatchBackend(namespace="bad namespace!!!")


def test_invalid_log_group(mock_boto3):
    from factory.telemetry.runtime.adapters.aws import AWSCloudWatchBackend

    with pytest.raises(ValueError, match="Invalid log_group"):
        AWSCloudWatchBackend(log_group="bad group!!!")


def test_health_check_ok(backend):
    backend._cw.list_metrics.return_value = {}
    h = backend.health_check()
    assert h["ok"] is True
    assert h["backend"] == "aws_cloudwatch"


def test_health_check_error(backend):
    backend._cw.list_metrics.side_effect = RuntimeError("cw fail")
    h = backend.health_check()
    assert h["ok"] is False
    assert "cw fail" in h["error"]


def test_record_metric_buffers(backend):
    backend.record_metric("cpu", 42.0, labels={"host": "a"})
    assert len(backend._metric_buffer) == 1
    assert backend._metric_buffer[0]["MetricName"] == "cpu"


def test_record_metric_flushes_at_20(backend):
    for i in range(20):
        backend.record_metric(f"m{i}", float(i))
    backend._cw.put_metric_data.assert_called_once()


def test_start_span(backend):
    span = backend.start_span("test-op", attributes={"k": "v"})
    assert isinstance(span, SpanData)
    assert span.name == "test-op"
    assert span.span_id in backend._active_spans


def test_end_span(backend):
    span = backend.start_span("op")
    backend.end_span(span)
    assert span.span_id not in backend._active_spans
    backend._xray.put_trace_segments.assert_called_once()


def test_end_span_with_error(backend):
    span = backend.start_span("op")
    backend.end_span(span, error="something broke")
    assert span.status == "ERROR"
    assert span.error_message == "something broke"


def test_record_log_buffers(backend):
    backend.record_log(Severity.INFO, "hello")
    assert len(backend._log_buffer) == 1


def test_record_log_flushes_at_25(backend):
    # Mock _ensure_log_stream to avoid side effects
    backend._stream_created = True
    backend._logs.put_log_events.return_value = {"nextSequenceToken": "t1"}
    for i in range(25):
        backend.record_log(Severity.INFO, f"msg {i}")
    backend._logs.put_log_events.assert_called_once()


def test_flush_both(backend):
    backend._stream_created = True
    backend._logs.put_log_events.return_value = {}
    backend.record_metric("m", 1.0)
    backend.record_log(Severity.ERROR, "err")
    backend.flush()
    backend._cw.put_metric_data.assert_called_once()
    backend._logs.put_log_events.assert_called_once()


def test_flush_empty_noop(backend):
    backend.flush()
    backend._cw.put_metric_data.assert_not_called()


def test_ensure_log_stream_creates(backend):
    backend._logs.exceptions = MagicMock()
    backend._logs.exceptions.ResourceAlreadyExistsException = type(
        "ResourceAlreadyExistsException", (Exception,), {},
    )
    backend._ensure_log_stream()
    assert backend._stream_created is True
    backend._logs.create_log_group.assert_called_once()
    backend._logs.create_log_stream.assert_called_once()


def test_ensure_log_stream_idempotent(backend):
    backend._stream_created = True
    backend._ensure_log_stream()
    backend._logs.create_log_group.assert_not_called()


def test_infrastructure_spec(backend):
    spec = backend.infrastructure_spec()
    assert spec["provider"] == "aws"
    assert "cloudwatch" in spec["services"]
    assert len(spec["resources"]) == 2
