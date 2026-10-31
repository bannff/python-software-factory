"""Protocol-buffer OTLP signal conversion owned by the Telemetry brick."""
from __future__ import annotations
import hashlib
from typing import Any, Literal
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import DecodeError
from opentelemetry.proto.collector.logs.v1 import logs_service_pb2
from opentelemetry.proto.collector.metrics.v1 import metrics_service_pb2
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2
from .provenance_models import (
    AuthenticatedTelemetryContext,
    TelemetryIngestBatch,
    TelemetryIngestItem,
)
from .trace_context import TraceContextModel, validate_w3c_carrier
OTLPSignal = Literal["traces", "logs", "metrics"]

class OTLPDecodeError(ValueError):
    """The receiver could not decode an OTLP protobuf payload."""

def _message_dict(message: Any) -> dict[str, Any]:
    return MessageToDict(message, preserving_proto_field_name=True)

def _any_value(value: Any) -> Any:
    kind = value.WhichOneof("value")
    if kind is None:
        return None
    raw = getattr(value, kind)
    if kind == "bytes_value":
        return raw.hex()
    if kind == "array_value":
        return [_any_value(item) for item in raw.values]
    if kind == "kvlist_value":
        return {item.key: _any_value(item.value) for item in raw.values}
    return raw

def _attributes(values: Any) -> dict[str, Any]:
    return {item.key: _any_value(item.value) for item in values}

def _id(value: bytes) -> str | None:
    return value.hex() if value else None

def _source_id(prefix: str, *parts: object) -> str:
    value = ":".join(str(part) for part in (prefix, *parts))
    if len(value) <= 256:
        return value
    return f"{prefix}:{hashlib.sha256(value.encode()).hexdigest()}"

def _payload(message: Any, resource: Any, scope: Any) -> dict[str, Any]:
    payload = _message_dict(message)
    if resource is not None:
        payload["resource"] = _message_dict(resource)
    if scope is not None:
        payload["scope"] = _message_dict(scope)
    return payload

def _trace_items(
    request: Any, trace_context: TraceContextModel | None,
) -> list[TelemetryIngestItem]:
    items: list[TelemetryIngestItem] = []
    for resource_index, resource_spans in enumerate(request.resource_spans):
        resource = resource_spans.resource
        for scope_index, scope_spans in enumerate(resource_spans.scope_spans):
            scope = scope_spans.scope
            for span_index, span in enumerate(scope_spans.spans):
                trace_id = _id(span.trace_id)
                span_id = _id(span.span_id)
                parent_id = _id(span.parent_span_id)
                tracestate = span.trace_state or None
                items.append(TelemetryIngestItem(
                    source_id=_source_id(
                        "span", trace_id or resource_index,
                        span_id or scope_index, span_index,
                    ),
                    canonical_payload=_payload(span, resource, scope),
                    trace_id=trace_id,
                    span_id=span_id,
                    parent_span_id=parent_id,
                    trace_flags=int(span.flags) & 0xFF,
                    tracestate=tracestate,
                    trace_context=trace_context,
                    signal="span",
                    attributes=_attributes(span.attributes),
                ))
    return items

def _log_items(
    request: Any, trace_context: TraceContextModel | None,
) -> list[TelemetryIngestItem]:
    items: list[TelemetryIngestItem] = []
    for resource_index, resource_logs in enumerate(request.resource_logs):
        resource = resource_logs.resource
        for scope_index, scope_logs in enumerate(resource_logs.scope_logs):
            scope = scope_logs.scope
            for log_index, log_record in enumerate(scope_logs.log_records):
                trace_id = _id(log_record.trace_id)
                span_id = _id(log_record.span_id)
                items.append(TelemetryIngestItem(
                    source_id=_source_id(
                        "log", trace_id or resource_index,
                        span_id or scope_index, log_index,
                    ),
                    canonical_payload=_payload(log_record, resource, scope),
                    trace_id=trace_id,
                    span_id=span_id,
                    trace_context=trace_context,
                    signal="log",
                    attributes=_attributes(log_record.attributes),
                ))
    return items

def _metric_items(
    request: Any, trace_context: TraceContextModel | None,
) -> list[TelemetryIngestItem]:
    items: list[TelemetryIngestItem] = []
    for resource_index, resource_metrics in enumerate(request.resource_metrics):
        resource = resource_metrics.resource
        for scope_index, scope_metrics in enumerate(resource_metrics.scope_metrics):
            scope = scope_metrics.scope
            for metric_index, metric in enumerate(scope_metrics.metrics):
                data_kind = metric.WhichOneof("data")
                if data_kind is None:
                    continue
                data = getattr(metric, data_kind)
                for point_index, point in enumerate(data.data_points):
                    timestamp = getattr(point, "time_unix_nano", 0)
                    items.append(TelemetryIngestItem(
                        source_id=_source_id(
                            "metric", metric.name, resource_index,
                            scope_index, metric_index, point_index, timestamp,
                        ),
                        canonical_payload={
                            "metric": _payload(metric, resource, scope),
                            "data_point": _message_dict(point),
                            "data_kind": data_kind,
                        },
                        trace_context=trace_context,
                        signal="metric",
                        attributes=_attributes(point.attributes),
                    ))
    return items

def _parse(signal: OTLPSignal, payload: bytes) -> Any:
    request_types = {
        "traces": trace_service_pb2.ExportTraceServiceRequest,
        "logs": logs_service_pb2.ExportLogsServiceRequest,
        "metrics": metrics_service_pb2.ExportMetricsServiceRequest,
    }
    try:
        request = request_types[signal]()
        request.ParseFromString(payload)
        return request
    except (KeyError, DecodeError, TypeError) as exc:
        raise OTLPDecodeError(f"invalid OTLP {signal} protobuf payload") from exc

def _carrier(value: object) -> TraceContextModel | None:
    if value is None:
        return None
    try:
        return value if isinstance(value, TraceContextModel) else validate_w3c_carrier(value)
    except ValueError as exc:
        raise OTLPDecodeError(f"invalid W3C trace context carrier: {exc}") from exc

def decode_otlp(
    signal: OTLPSignal,
    payload: bytes,
    context: AuthenticatedTelemetryContext,
    batch_id: str | None = None,
    carrier: dict[str, str] | TraceContextModel | None = None,
) -> TelemetryIngestBatch:
    """Convert an authenticated OTLP body to the ordinary Telemetry DTO."""
    context = AuthenticatedTelemetryContext.model_validate(context)
    if not isinstance(payload, bytes):
        raise OTLPDecodeError("OTLP payload must be protobuf bytes")
    request = _parse(signal, payload)
    trace_context = _carrier(carrier)
    items = {
        "traces": _trace_items,
        "logs": _log_items,
        "metrics": _metric_items,
    }[signal](request, trace_context)
    if not batch_id:
        digest = hashlib.sha256(
            context.tenant_id.encode() + b"\0" +
            context.producer_id.encode() + b"\0" + signal.encode() + payload,
        ).hexdigest()
        batch_id = f"otlp-{digest}"
    return TelemetryIngestBatch(batch_id=batch_id, items=items)

__all__ = ["OTLPDecodeError", "OTLPSignal", "decode_otlp"]
