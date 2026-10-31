"""Reconstruct OTEL ReadableSpan objects from JSON for MCP transport.

The agent brick exports spans via ReadableSpan.to_json() (OTEL SDK
built-in). This adapter reconstructs them so
StrandsInMemorySessionMapper.map_to_session() can produce a canonical
Strands Session — no custom serialization format needed.
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def spans_from_json(span_jsons: list[str]) -> list[Any]:
    """Reconstruct ReadableSpan objects from OTEL JSON strings.

    Each string is the output of ReadableSpan.to_json() which produces
    a well-defined JSON with: name, context (trace_id, span_id),
    parent_id, start_time, end_time, attributes, events, links, kind,
    resource, status.

    Returns objects compatible with StrandsInMemorySessionMapper.
    """
    from opentelemetry.sdk.trace import ReadableSpan
    from opentelemetry.trace import SpanContext, SpanKind, TraceFlags
    from opentelemetry.trace.status import Status, StatusCode
    from opentelemetry.sdk.trace import Event
    from opentelemetry.sdk.resources import Resource

    spans = []
    for raw in span_jsons:
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
            spans.append(_build_span(data, ReadableSpan, SpanContext,
                                     SpanKind, TraceFlags, Status,
                                     StatusCode, Event, Resource))
        except Exception as e:
            logger.warning("Failed to reconstruct span: %s", e)
    return spans


def _build_span(data, ReadableSpan, SpanContext, SpanKind, TraceFlags,
                Status, StatusCode, Event, Resource):
    """Build a single ReadableSpan from parsed JSON dict."""
    ctx = data.get("context", {})
    trace_id = int(ctx.get("trace_id", "0"), 16) if ctx.get("trace_id") else 0
    span_id = int(ctx.get("span_id", "0"), 16) if ctx.get("span_id") else 0
    trace_flags = TraceFlags(ctx.get("trace_flags", 1))

    parent_id = data.get("parent_id")
    parent = None
    if parent_id:
        parent = SpanContext(
            trace_id=trace_id,
            span_id=int(parent_id, 16) if isinstance(parent_id, str) else parent_id,
            is_remote=True, trace_flags=trace_flags,
        )

    kind_map = {
        "SpanKind.INTERNAL": SpanKind.INTERNAL,
        "SpanKind.SERVER": SpanKind.SERVER,
        "SpanKind.CLIENT": SpanKind.CLIENT,
        "SpanKind.PRODUCER": SpanKind.PRODUCER,
        "SpanKind.CONSUMER": SpanKind.CONSUMER,
    }
    kind = kind_map.get(str(data.get("kind", "")), SpanKind.INTERNAL)

    status_data = data.get("status", {})
    status_code_str = status_data.get("status_code", "UNSET")
    code_map = {"UNSET": StatusCode.UNSET, "OK": StatusCode.OK,
                "ERROR": StatusCode.ERROR}
    status = Status(code_map.get(status_code_str, StatusCode.UNSET),
                    status_data.get("description"))

    attrs = data.get("attributes", {}) or {}
    resource_data = data.get("resource", {})
    resource_attrs = resource_data.get("attributes", {}) if resource_data else {}
    resource = Resource(attributes=resource_attrs) if resource_attrs else Resource.create()

    events = []
    for ev in data.get("events", []) or []:
        events.append(Event(
            name=ev.get("name", ""),
            attributes=ev.get("attributes", {}),
            timestamp=ev.get("timestamp", 0),
        ))

    span_context = SpanContext(
        trace_id=trace_id, span_id=span_id,
        is_remote=False, trace_flags=trace_flags,
    )

    return ReadableSpan(
        name=data.get("name", ""),
        context=span_context,
        parent=parent,
        resource=resource,
        attributes=attrs,
        events=tuple(events),
        links=(),
        kind=kind,
        status=status,
        start_time=data.get("start_time", 0),
        end_time=data.get("end_time", 0),
    )


def session_from_otel_json(
    span_jsons: list[str], session_id: str = "unknown",
) -> dict[str, Any]:
    """Normalize OTEL JSON as framework-neutral session evidence."""
    spans = []
    for raw in span_jsons:
        value = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(value, dict):
            spans.append(value)
    return {
        "session_id": session_id,
        "traces": [{"trace_id": session_id, "spans": spans}],
    }
