"""AWS CloudWatch + X-Ray adapter for telemetry brick.

Implements TelemetryBackend protocol using CloudWatch for metrics,
X-Ray for traces, and CloudWatch Logs for log entries.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from factory.telemetry.runtime.ports import (
    LogEntry,
    MetricValue,
    Severity,
    SpanData,
)


def _require_boto3() -> None:
    try:
        import boto3  # noqa: F401
    except ImportError:
        msg = "pip install boto3 — required for AWS telemetry adapter"
        raise ImportError(msg)


_NS_RE = re.compile(r"^[A-Za-z0-9._/#:-]{1,256}$")
_LOG_GROUP_RE = re.compile(r"^[A-Za-z0-9._/\\#-]{1,512}$")


class AWSCloudWatchBackend:
    """AWS CloudWatch + X-Ray adapter for TelemetryBackend port."""

    def __init__(
        self,
        namespace: str = "Factory",
        log_group: str = "/factory/telemetry",
        region: str = "us-east-1",
        **kwargs: Any,
    ) -> None:
        _require_boto3()
        if not _NS_RE.match(namespace):
            raise ValueError(f"Invalid namespace: {namespace!r}")
        if not _LOG_GROUP_RE.match(log_group):
            raise ValueError(f"Invalid log_group: {log_group!r}")
        import boto3
        self._cw = boto3.client("cloudwatch", region_name=region)
        self._xray = boto3.client("xray", region_name=region)
        self._logs = boto3.client("logs", region_name=region)
        self._namespace = namespace
        self._log_group = log_group
        self._region = region
        self._active_spans: dict[str, SpanData] = {}
        self._metric_buffer: list[dict] = []
        self._log_buffer: list[dict] = []
        self._log_stream = f"telemetry-{uuid.uuid4().hex[:8]}"
        self._seq_token: str | None = None
        self._stream_created = False

    def _ensure_log_stream(self) -> None:
        if self._stream_created:
            return
        try:
            self._logs.create_log_group(logGroupName=self._log_group)
        except self._logs.exceptions.ResourceAlreadyExistsException:
            pass
        try:
            self._logs.create_log_stream(
                logGroupName=self._log_group, logStreamName=self._log_stream,
            )
        except self._logs.exceptions.ResourceAlreadyExistsException:
            pass
        self._stream_created = True

    def record_metric(
        self, name: str, value: float, labels: dict[str, str] | None = None,
    ) -> None:
        dims = [{"Name": k, "Value": v} for k, v in (labels or {}).items()]
        self._metric_buffer.append({
            "MetricName": name, "Value": value,
            "Dimensions": dims, "Timestamp": datetime.now(timezone.utc),
            "Unit": "None",
        })
        if len(self._metric_buffer) >= 20:
            self._flush_metrics()

    def _flush_metrics(self) -> None:
        if not self._metric_buffer:
            return
        # CloudWatch accepts max 1000 per call; batch in chunks of 20
        batch = self._metric_buffer[:20]
        self._metric_buffer = self._metric_buffer[20:]
        try:
            self._cw.put_metric_data(Namespace=self._namespace, MetricData=batch)
        except Exception:
            pass  # best-effort

    def start_span(
        self, name: str, attributes: dict[str, Any] | None = None,
    ) -> SpanData:
        span = SpanData(
            trace_id=uuid.uuid4().hex,
            span_id=uuid.uuid4().hex[:16],
            name=name,
            start_time=datetime.now(timezone.utc).timestamp(),
            attributes=attributes or {},
        )
        self._active_spans[span.span_id] = span
        return span

    def end_span(self, span: SpanData, error: str | None = None) -> None:
        span.end_time = datetime.now(timezone.utc).timestamp()
        if error:
            span.status = "ERROR"
            span.error_message = error
        self._active_spans.pop(span.span_id, None)
        try:
            segment = {
                "trace_id": f"1-{int(span.start_time):08x}-{span.trace_id[:24]}",
                "id": span.span_id, "name": span.name,
                "start_time": span.start_time, "end_time": span.end_time,
                "annotations": span.attributes,
            }
            if error:
                segment["fault"] = True
                segment["cause"] = {"message": error}
            self._xray.put_trace_segments(
                TraceSegmentDocuments=[json.dumps(segment)],
            )
        except Exception:
            pass  # best-effort

    def record_log(
        self, severity: Severity, body: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        self._log_buffer.append({
            "timestamp": int(time.time() * 1000),
            "message": json.dumps({
                "severity": severity.value, "body": body,
                "attributes": attributes or {},
            }),
        })
        if len(self._log_buffer) >= 25:
            self._flush_logs()

    def _flush_logs(self) -> None:
        if not self._log_buffer:
            return
        self._ensure_log_stream()
        kwargs: dict[str, Any] = {
            "logGroupName": self._log_group,
            "logStreamName": self._log_stream,
            "logEvents": sorted(self._log_buffer, key=lambda e: e["timestamp"]),
        }
        if self._seq_token:
            kwargs["sequenceToken"] = self._seq_token
        try:
            resp = self._logs.put_log_events(**kwargs)
            self._seq_token = resp.get("nextSequenceToken")
        except Exception:
            pass  # best-effort
        self._log_buffer.clear()

    def flush(self) -> None:
        self._flush_metrics()
        self._flush_logs()

    def health_check(self) -> dict[str, Any]:
        try:
            self._cw.list_metrics(Namespace=self._namespace, Limit=1)
            return {"ok": True, "backend": "aws_cloudwatch", "namespace": self._namespace}
        except Exception as e:
            return {"ok": False, "backend": "aws_cloudwatch", "error": str(e)}

    def infrastructure_spec(self) -> dict[str, Any]:
        return {
            "provider": "aws",
            "services": ["cloudwatch", "xray", "logs"],
            "resources": [
                {"type": "AWS::CloudWatch::Namespace", "properties": {
                    "Namespace": self._namespace}},
                {"type": "AWS::Logs::LogGroup", "properties": {
                    "LogGroupName": self._log_group}},
            ],
        }
