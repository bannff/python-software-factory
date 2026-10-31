"""Recording operations for telemetry (LLM, agent, tool, logs, spans)."""

from __future__ import annotations

import uuid
from typing import Any, Literal, TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry._logs import SeverityNumber
from factory.mcp_utils.interface import sanitize_protected, telemetry_attributes
from factory.mcp_utils.protected_persistence import safe_exception

if TYPE_CHECKING:
    from .runtime import TelemetryRuntime

SEVERITY_MAP: dict[str, SeverityNumber] = {
    "DEBUG": SeverityNumber.DEBUG,
    "INFO": SeverityNumber.INFO,
    "WARN": SeverityNumber.WARN,
    "WARNING": SeverityNumber.WARN,
    "ERROR": SeverityNumber.ERROR,
}


def record_log(
    runtime: "TelemetryRuntime",
    severity: Literal["DEBUG", "INFO", "WARN", "WARNING", "ERROR"],
    body: str,
    attributes: dict[str, Any] | None,
    trace_id: str | None = None,
    span_id: str | None = None,
) -> dict[str, Any]:
    """Record a log entry via OTLP."""
    body = str(sanitize_protected({"body": body})["body"])
    attributes = telemetry_attributes(attributes or {})
    runtime.state.snapshot.logs.total += 1
    sev_key = severity.upper()
    if sev_key == "WARNING":
        sev_key = "WARN"
    runtime.state.snapshot.logs.by_severity[sev_key] = (
        runtime.state.snapshot.logs.by_severity.get(sev_key, 0) + 1
    )

    if runtime._logger:
        severity_number = SEVERITY_MAP.get(severity.upper(), SeverityNumber.INFO)
        runtime._logger.emit(
            body=body,
            severity_number=severity_number,
            attributes=attributes or {},
        )

    return {"ok": True, "recorded": "log"}


def record_llm_interaction(
    runtime: "TelemetryRuntime",
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: float | None,
    cost_usd: float | None,
    agent_id: str | None,
    workflow_id: str | None,
    trace_attributes: dict[str, Any] | None,
) -> dict[str, Any]:
    """Record an LLM interaction with tokens, latency, and cost."""
    attrs = telemetry_attributes({
        "model": model,
        **({"agent_id": agent_id} if agent_id else {}),
        **({"workflow_id": workflow_id} if workflow_id else {}),
        **(trace_attributes or {}),
    })

    runtime.state.snapshot.llm_interactions += 1
    runtime.state.snapshot.llm_input_tokens += int(input_tokens)
    runtime.state.snapshot.llm_output_tokens += int(output_tokens)
    if cost_usd is not None:
        runtime.state.snapshot.llm_cost_usd += float(cost_usd)
    if latency_ms is not None:
        runtime.state.snapshot.last_latency_ms = float(latency_ms)

    total_tokens = int(input_tokens) + int(output_tokens)
    if runtime._counter_llm_tokens:
        runtime._counter_llm_tokens.add(total_tokens, attributes=attrs)
    if latency_ms is not None and runtime._hist_llm_latency_ms:
        runtime._hist_llm_latency_ms.record(float(latency_ms), attributes=attrs)

    if runtime._tracer:
        with runtime._tracer.start_as_current_span("llm.interaction", attributes=attrs) as span:
            span.set_attribute("llm.input_tokens", int(input_tokens))
            span.set_attribute("llm.output_tokens", int(output_tokens))
            span.set_attribute("llm.total_tokens", total_tokens)
            if cost_usd is not None:
                span.set_attribute("llm.cost_usd", float(cost_usd))
            if latency_ms is not None:
                span.set_attribute("llm.latency_ms", float(latency_ms))

    return {"ok": True, "recorded": "llm_interaction"}


def record_agent_execution(
    runtime: "TelemetryRuntime",
    agent_id: str,
    workflow_id: str,
    success: bool,
    latency_ms: float | None,
    trace_attributes: dict[str, Any] | None,
) -> dict[str, Any]:
    """Record an agent execution event."""
    attrs = telemetry_attributes({
        "agent_id": agent_id,
        "workflow_id": workflow_id,
        **(trace_attributes or {}),
    })

    runtime.state.snapshot.agent_executions += 1
    if not success:
        runtime.state.snapshot.errors += 1

    if runtime._counter_agent_exec:
        runtime._counter_agent_exec.add(1, attributes=attrs)

    if runtime._tracer:
        with runtime._tracer.start_as_current_span("agent.execution", attributes=attrs) as span:
            span.set_attribute("success", bool(success))
            if latency_ms is not None:
                span.set_attribute("latency_ms", float(latency_ms))
            if not success:
                span.set_status(Status(StatusCode.ERROR))

    return {"ok": True, "recorded": "agent_execution"}


def record_tool_invocation(
    runtime: "TelemetryRuntime",
    tool_name: str,
    workflow_id: str | None,
    success: bool,
    latency_ms: float | None,
    trace_attributes: dict[str, Any] | None,
) -> dict[str, Any]:
    """Record a tool invocation event."""
    attrs = telemetry_attributes({
        "tool_name": tool_name,
        **({"workflow_id": workflow_id} if workflow_id else {}),
        **(trace_attributes or {}),
    })

    runtime.state.snapshot.tool_invocations += 1
    if not success:
        runtime.state.snapshot.errors += 1

    if runtime._counter_tool_invocations:
        runtime._counter_tool_invocations.add(1, attributes=attrs)

    if runtime._tracer:
        with runtime._tracer.start_as_current_span("tool.invocation", attributes=attrs) as span:
            span.set_attribute("success", bool(success))
            if latency_ms is not None:
                span.set_attribute("latency_ms", float(latency_ms))
            if not success:
                span.set_status(Status(StatusCode.ERROR))

    return {"ok": True, "recorded": "tool_invocation"}


def start_span(
    runtime: "TelemetryRuntime",
    name: str,
    attributes: dict[str, Any] | None,
) -> dict[str, Any]:
    """Start a new span and return its ID."""
    if not runtime._tracer:
        return {"ok": False, "error": "tracer_not_initialized"}
    span = runtime._tracer.start_span(name, attributes=telemetry_attributes(attributes or {}))
    span_id = str(uuid.uuid4())
    runtime.state.spans[span_id] = span
    return {"ok": True, "span_id": span_id}


def end_span(
    runtime: "TelemetryRuntime",
    span_id: str,
    error: str | None,
) -> dict[str, Any]:
    """End a span by ID, optionally recording an error."""
    span = runtime.state.spans.pop(span_id, None)
    if span is None:
        return {"ok": False, "error": "span_not_found", "span_id": span_id}
    if error:
        safe_error = safe_exception(RuntimeError(error))
        span.record_exception(safe_error)
        span.set_status(Status(StatusCode.ERROR, description=str(safe_error)))
        runtime.state.snapshot.errors += 1
    span.end()
    return {"ok": True, "span_id": span_id}
