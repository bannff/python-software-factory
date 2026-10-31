"""Operational OpenTelemetry recording tools."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING, Literal

from factory.mcp_utils.decorators import operational
from factory.mcp_utils.registration import typed_tool
from factory.mcp_utils.runtime.tool_result import ToolResult

from .contracts.base import JsonObject
from .contracts.operational import (
    AgentExecutionInput, EndSpanInput, FlushInput, FlushOutput,
    LlmInteractionInput, RecordLogInput, RecordedOutput, RetentionInput,
    RetentionOutput, SpanOutput,
    StartSpanInput, ToolInvocationInput,
)
from ..runtime.policy_config import compose_retention_days
from .provenance import register as register_provenance

if TYPE_CHECKING:
    from ..runtime.runtime import TelemetryRuntime


def register(mcp: Any, runtime: "TelemetryRuntime") -> None:
    """Register normalized recording and export tools."""

    @typed_tool(mcp)
    @operational(input_model=FlushInput, output_model=FlushOutput)
    def flush_telemetry(timeout_ms: int = 5000) -> ToolResult[FlushOutput]:
        return runtime.flush_telemetry(timeout_ms=timeout_ms)

    _default_raw_days, _default_rollup_days = compose_retention_days()

    @typed_tool(mcp)
    @operational(input_model=RetentionInput, output_model=RetentionOutput)
    def telemetry_run_retention(
        raw_days: int = _default_raw_days, rollup_days: int = _default_rollup_days,
        compact_source: bool = True,
    ) -> ToolResult[RetentionOutput]:
        result = runtime.run_retention(
            raw_days=raw_days, rollup_days=rollup_days,
            compact_source=compact_source,
        )
        return RetentionOutput.model_validate(result.model_dump())

    @typed_tool(mcp)
    @operational(input_model=RecordLogInput, output_model=RecordedOutput)
    def record_log(
        severity: Literal["DEBUG", "INFO", "WARN", "WARNING", "ERROR"],
        body: str, attributes: dict[str, Any] | None = None,
        trace_id: str | None = None, span_id: str | None = None,
    ) -> ToolResult[RecordedOutput]:
        return runtime.record_log(
            severity=severity, body=body, attributes=attributes,
            trace_id=trace_id, span_id=span_id,
        )

    @typed_tool(mcp)
    @operational(input_model=LlmInteractionInput, output_model=RecordedOutput)
    def record_llm_interaction(
        model: str, input_tokens: int, output_tokens: int,
        latency_ms: float | None = None, cost_usd: float | None = None,
        agent_id: str | None = None, workflow_id: str | None = None,
        trace_attributes: JsonObject | None = None,
    ) -> ToolResult[RecordedOutput]:
        return runtime.record_llm_interaction(
            model, input_tokens, output_tokens, latency_ms, cost_usd,
            agent_id, workflow_id, trace_attributes,
        )

    @typed_tool(mcp)
    @operational(input_model=AgentExecutionInput, output_model=RecordedOutput)
    def record_agent_execution(
        agent_id: str, workflow_id: str, success: bool = True,
        latency_ms: float | None = None,
        trace_attributes: JsonObject | None = None,
    ) -> ToolResult[RecordedOutput]:
        return runtime.record_agent_execution(
            agent_id, workflow_id, success, latency_ms, trace_attributes,
        )

    @typed_tool(mcp)
    @operational(input_model=ToolInvocationInput, output_model=RecordedOutput)
    def record_tool_invocation(
        tool_name: str, workflow_id: str | None = None, success: bool = True,
        latency_ms: float | None = None,
        trace_attributes: JsonObject | None = None,
    ) -> ToolResult[RecordedOutput]:
        return runtime.record_tool_invocation(
            tool_name, workflow_id, success, latency_ms, trace_attributes,
        )

    @typed_tool(mcp)
    @operational(input_model=StartSpanInput, output_model=SpanOutput)
    def start_span(
        name: str, attributes: JsonObject | None = None,
    ) -> ToolResult[SpanOutput]:
        return runtime.start_span(name, attributes)

    @typed_tool(mcp)
    @operational(input_model=EndSpanInput, output_model=SpanOutput)
    def end_span(span_id: str, error: str | None = None) -> ToolResult[SpanOutput]:
        return runtime.end_span(span_id, error)

    register_provenance(mcp, runtime)
