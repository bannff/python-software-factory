"""Validated trace-context operations used by the Telemetry runtime."""
from __future__ import annotations

from typing import Any

from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from .trace_context import TraceContextOutput, validate_w3c_carrier


def _output(parsed: Any, outcome: str) -> dict[str, Any]:
    return TraceContextOutput(
        ok=True,
        outcome=outcome,
        carrier=parsed.carrier,
        traceparent=parsed.traceparent,
        traceparent_version=parsed.traceparent_version,
        trace_id=parsed.trace_id,
        span_id=parsed.span_id,
        trace_flags=parsed.trace_flags,
        tracestate=parsed.tracestate,
    ).model_dump()


def inject_context(propagator: TraceContextTextMapPropagator) -> dict[str, Any]:
    carrier: dict[str, str] = {}
    propagator.inject(carrier)
    if not carrier.get("traceparent"):
        return TraceContextOutput(
            ok=False, outcome="no_context", carrier=carrier,
            error="no_active_trace_context",
        ).model_dump()
    try:
        return _output(validate_w3c_carrier(carrier), "injected")
    except ValueError as exc:
        return TraceContextOutput(
            ok=False, outcome="rejected", carrier=None, error=str(exc),
        ).model_dump()


def extract_context(
    propagator: TraceContextTextMapPropagator, carrier: dict[str, str],
) -> dict[str, Any]:
    try:
        parsed = validate_w3c_carrier(carrier)
        extraction_carrier = {
            key.lower(): value for key, value in parsed.carrier.items()
        }
        ctx = propagator.extract(extraction_carrier)
        span_ctx = trace.get_current_span(ctx).get_span_context()
        if not span_ctx.is_valid:
            raise ValueError("untrusted trace context")
        return _output(parsed, "extracted")
    except (TypeError, ValueError) as exc:
        return TraceContextOutput(
            ok=False, outcome="rejected", error=str(exc),
        ).model_dump()


__all__ = ["extract_context", "inject_context"]
