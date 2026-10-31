"""Tests for CloudWatch Logs logger adapter."""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from factory.logger.runtime.ports import LogLevel, LogRecord


@pytest.fixture
def mock_boto3():
    with patch("boto3.client") as mc:
        mc.return_value = MagicMock()
        yield mc


@pytest.fixture
def sink(mock_boto3):
    from factory.logger.runtime.adapters.aws import CloudWatchLogSink

    return CloudWatchLogSink(log_group="/test/logs", log_stream="test-stream")


@pytest.fixture
def record():
    return LogRecord(
        level=LogLevel.INFO, message="hello",
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        logger_name="test", source="unit", run_id="r1", tenant_id="t1",
    )


def test_invalid_log_group(mock_boto3):
    from factory.logger.runtime.adapters.aws import CloudWatchLogSink

    with pytest.raises(ValueError, match="Invalid log_group"):
        CloudWatchLogSink(log_group="bad group!!!")


def test_invalid_log_stream(mock_boto3):
    from factory.logger.runtime.adapters.aws import CloudWatchLogSink

    with pytest.raises(ValueError, match="Invalid log_stream"):
        CloudWatchLogSink(log_group="/ok", log_stream="bad stream!!!")


def test_write_buffers(sink, record):
    sink.write(record)
    assert len(sink._buffer) == 1


def test_write_flushes_at_buffer_size(sink, record):
    sink._stream_created = True
    sink._client.put_log_events.return_value = {"nextSequenceToken": "t1"}
    for _ in range(25):
        sink.write(record)
    sink._client.put_log_events.assert_called_once()
    assert len(sink._buffer) == 0


def test_flush_empty_noop(sink):
    sink.flush()
    sink._client.put_log_events.assert_not_called()


def test_flush_sends_sorted(sink, record):
    sink._stream_created = True
    sink._client.put_log_events.return_value = {}
    sink.write(record)
    sink.flush()
    call_kwargs = sink._client.put_log_events.call_args[1]
    assert call_kwargs["logGroupName"] == "/test/logs"
    assert call_kwargs["logStreamName"] == "test-stream"
    assert len(sink._buffer) == 0


def test_flush_with_seq_token(sink, record):
    sink._stream_created = True
    sink._seq_token = "prev-token"
    sink._client.put_log_events.return_value = {"nextSequenceToken": "new-token"}
    sink.write(record)
    sink.flush()
    call_kwargs = sink._client.put_log_events.call_args[1]
    assert call_kwargs["sequenceToken"] == "prev-token"
    assert sink._seq_token == "new-token"


def test_flush_exception_clears_buffer(sink, record):
    sink._stream_created = True
    sink._client.put_log_events.side_effect = Exception("fail")
    sink.write(record)
    sink.flush()
    assert len(sink._buffer) == 0  # cleared even on error


def test_close_flushes(sink, record):
    sink._stream_created = True
    sink._client.put_log_events.return_value = {}
    sink.write(record)
    sink.close()
    sink._client.put_log_events.assert_called_once()


def test_health_check_ok(sink):
    sink._client.describe_log_groups.return_value = {}
    h = sink.health_check()
    assert h["writable"] is True
    assert h["backend"] == "cloudwatch_logs"


def test_health_check_error(sink):
    sink._client.describe_log_groups.side_effect = RuntimeError("no access")
    h = sink.health_check()
    assert h["writable"] is False
    assert "no access" in h["error"]


def test_ensure_stream_creates(sink):
    sink._client.exceptions = MagicMock()
    sink._client.exceptions.ResourceAlreadyExistsException = type(
        "ResourceAlreadyExistsException", (Exception,), {},
    )
    sink._ensure_stream()
    assert sink._stream_created is True
    sink._client.create_log_group.assert_called_once()
    sink._client.create_log_stream.assert_called_once()


def test_ensure_stream_idempotent(sink):
    sink._stream_created = True
    sink._ensure_stream()
    sink._client.create_log_group.assert_not_called()


def test_infrastructure_spec(sink):
    spec = sink.infrastructure_spec()
    assert spec["provider"] == "aws"
    assert spec["service"] == "logs"
    assert len(spec["resources"]) == 2


def test_default_stream_name_generated(mock_boto3):
    from factory.logger.runtime.adapters.aws import CloudWatchLogSink

    s = CloudWatchLogSink(log_group="/test/logs")
    assert s._log_stream.startswith("factory-")
