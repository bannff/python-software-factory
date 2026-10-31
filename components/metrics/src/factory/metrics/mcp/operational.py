"""Typed operational MCP tools for Metrics."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from factory.mcp_utils.interface import ToolResult, operational, ok
from factory.mcp_utils.registration import typed_tool

from .contracts.operational import (
    AggregationInput, AggregationOutput, DriftInput, DriftOutput, RecordBatchInput,
    RecordBatchOutput, RecordInput, RecordOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import MetricsRuntime


def _result(value: dict[str, Any], model: type[Any]) -> ToolResult[Any]:
    return ok(model.model_validate(value))


def register(mcp: Any, runtime: "MetricsRuntime") -> None:
    """Register stateful Metrics tools with strict flat ingress."""

    @typed_tool(mcp)
    @operational(input_model=RecordInput, output_model=RecordOutput)
    def metrics_record(metric_id: str, value: float, labels: dict[str, str] | None = None) -> ToolResult[RecordOutput]:
        return _result(runtime.record(metric_id, value, labels), RecordOutput)

    @typed_tool(mcp)
    @operational(input_model=RecordBatchInput, output_model=RecordBatchOutput)
    def metrics_record_batch(records: list[dict[str, Any]]) -> ToolResult[RecordBatchOutput]:
        return _result(runtime.record_batch(records), RecordBatchOutput)

    @typed_tool(mcp)
    @operational(input_model=AggregationInput, output_model=AggregationOutput)
    def metrics_compute_aggregation(metric_id: str, method: str = "mean", period: str = "24h") -> ToolResult[AggregationOutput]:
        return _result(runtime.compute_aggregation(metric_id, method, period), AggregationOutput)

    @typed_tool(mcp)
    @operational(input_model=DriftInput, output_model=DriftOutput)
    def metrics_detect_drift(metric_id: str, baseline_period: str = "7d", current_period: str = "24h", threshold: float = 0.1) -> ToolResult[DriftOutput]:
        return _result(runtime.detect_drift(metric_id, baseline_period, current_period, threshold), DriftOutput)
