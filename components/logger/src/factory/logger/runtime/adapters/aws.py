"""AWS CloudWatch Logs adapter for logger brick.

Implements LogSink protocol using CloudWatch Logs.
Buffers log entries and flushes in batches via put_log_events.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any

from factory.logger.runtime.ports import LogLevel, LogRecord


def _require_boto3() -> None:
    try:
        import boto3  # noqa: F401
    except ImportError:
        msg = "pip install boto3 — required for AWS logger adapter"
        raise ImportError(msg)


_LOG_GROUP_RE = re.compile(r"^[A-Za-z0-9._/\\#-]{1,512}$")
_LOG_STREAM_RE = re.compile(r"^[A-Za-z0-9._/\\#-]{1,512}$")

_LEVEL_MAP = {
    LogLevel.DEBUG: "DEBUG",
    LogLevel.INFO: "INFO",
    LogLevel.WARNING: "WARNING",
    LogLevel.ERROR: "ERROR",
    LogLevel.CRITICAL: "CRITICAL",
}


class CloudWatchLogSink:
    """CloudWatch Logs adapter for LogSink port.

    Buffers log records and flushes in batches to CloudWatch Logs.
    """

    def __init__(
        self,
        log_group: str = "/factory/logs",
        log_stream: str = "",
        region: str = "us-east-1",
        buffer_size: int = 25,
        **kwargs: Any,
    ) -> None:
        _require_boto3()
        if not _LOG_GROUP_RE.match(log_group):
            raise ValueError(f"Invalid log_group: {log_group!r}")
        stream = log_stream or f"factory-{uuid.uuid4().hex[:8]}"
        if not _LOG_STREAM_RE.match(stream):
            raise ValueError(f"Invalid log_stream: {stream!r}")
        import boto3
        self._client = boto3.client("logs", region_name=region)
        self._log_group = log_group
        self._log_stream = stream
        self._region = region
        self._buffer: list[dict] = []
        self._buffer_size = buffer_size
        self._seq_token: str | None = None
        self._stream_created = False

    def _ensure_stream(self) -> None:
        if self._stream_created:
            return
        try:
            self._client.create_log_group(logGroupName=self._log_group)
        except self._client.exceptions.ResourceAlreadyExistsException:
            pass
        try:
            self._client.create_log_stream(
                logGroupName=self._log_group, logStreamName=self._log_stream,
            )
        except self._client.exceptions.ResourceAlreadyExistsException:
            pass
        self._stream_created = True

    def write(self, record: LogRecord) -> None:
        entry = {
            "timestamp": int(record.timestamp.timestamp() * 1000),
            "message": json.dumps({
                "level": _LEVEL_MAP.get(record.level, "INFO"),
                "message": record.message,
                "logger": record.logger_name,
                "source": record.source,
                "run_id": record.run_id,
                "tenant_id": record.tenant_id,
                "context": record.context,
            }),
        }
        self._buffer.append(entry)
        if len(self._buffer) >= self._buffer_size:
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return
        self._ensure_stream()
        events = sorted(self._buffer, key=lambda e: e["timestamp"])
        kwargs: dict[str, Any] = {
            "logGroupName": self._log_group,
            "logStreamName": self._log_stream,
            "logEvents": events,
        }
        if self._seq_token:
            kwargs["sequenceToken"] = self._seq_token
        try:
            resp = self._client.put_log_events(**kwargs)
            self._seq_token = resp.get("nextSequenceToken")
        except Exception:
            pass  # best-effort; don't crash the app on log failure
        self._buffer.clear()

    def close(self) -> None:
        self.flush()

    def health_check(self) -> dict[str, Any]:
        try:
            self._client.describe_log_groups(
                logGroupNamePrefix=self._log_group, limit=1,
            )
            return {
                "writable": True, "backend": "cloudwatch_logs",
                "log_group": self._log_group,
            }
        except Exception as e:
            return {
                "writable": False, "backend": "cloudwatch_logs",
                "error": str(e),
            }

    def infrastructure_spec(self) -> dict[str, Any]:
        return {
            "provider": "aws",
            "service": "logs",
            "resources": [{
                "type": "AWS::Logs::LogGroup",
                "properties": {"LogGroupName": self._log_group},
            }, {
                "type": "AWS::Logs::LogStream",
                "properties": {
                    "LogGroupName": self._log_group,
                    "LogStreamName": self._log_stream,
                },
            }],
        }
