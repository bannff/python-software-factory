"""Typed deterministic MCP tools for the Metrics brick."""
from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from pydantic import JsonValue
from factory.mcp_utils.interface import ToolResult, deterministic, ok
from factory.mcp_utils.registration import typed_tool

from .contracts.deterministic import (
    AllSnapshotsInput,
    AllSnapshotsOutput,
    BaselineComparisonOutput,
    BaselinesOutput,
    CapabilitiesOutput,
    CompareBaselineInput,
    ConfigSchemaOutput,
    DefinitionOutput,
    EmptyInput,
    HealthOutput,
    ListBaselinesInput,
    MetricIdInput,
    RegistryOutput,
    SnapshotInput,
    SnapshotOutput,
    TaxonomyInput,
    TaxonomyOutput,
    TrendInput,
    TrendOutput,
)
from .contracts.provenance import MeasureInput, MeasureOutput

if TYPE_CHECKING:
    from ..runtime.runtime import MetricsRuntime


def register(mcp: Any, runtime: "MetricsRuntime") -> None:
    """Register deterministic tools with strict flat ingress."""
    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def metrics_get_capabilities() -> ToolResult[CapabilitiesOutput]:
        return ok(CapabilitiesOutput.model_validate(runtime.get_capabilities()))
    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def metrics_health_check() -> ToolResult[HealthOutput]:
        return ok(HealthOutput.model_validate(runtime.health_check()))
    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def metrics_describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        return ok(ConfigSchemaOutput.model_validate(runtime.describe_config_schema()))
    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=RegistryOutput)
    def metrics_get_registry() -> ToolResult[RegistryOutput]:
        return ok(RegistryOutput(definitions=runtime.list_definitions()))
    @typed_tool(mcp)
    @deterministic(input_model=MetricIdInput, output_model=DefinitionOutput)
    def metrics_get_definition(metric_id: str) -> ToolResult[DefinitionOutput]:
        definition = runtime.get_definition(metric_id)
        return ok(DefinitionOutput(ok=definition is not None, definition=definition,
            error=None if definition else f"Definition not found: {metric_id}"))
    @typed_tool(mcp)
    @deterministic(input_model=SnapshotInput, output_model=SnapshotOutput)
    def metrics_get_snapshot(metric_id: str, period: str = "24h") -> ToolResult[SnapshotOutput]:
        return ok(SnapshotOutput.model_validate(runtime.get_snapshot(metric_id, period)))
    @typed_tool(mcp)
    @deterministic(input_model=TrendInput, output_model=TrendOutput)
    def metrics_get_trend(metric_id: str, window: str = "7d", granularity: str = "1d") -> ToolResult[TrendOutput]:
        return ok(TrendOutput.model_validate(runtime.get_trend(metric_id, window, granularity)))
    @typed_tool(mcp)
    @deterministic(input_model=AllSnapshotsInput, output_model=AllSnapshotsOutput)
    def metrics_get_all_snapshots(period: str = "24h") -> ToolResult[AllSnapshotsOutput]:
        items = [{**d, "snapshot": runtime.get_snapshot(d["id"], period)} for d in runtime.list_definitions()]
        return ok(AllSnapshotsOutput(snapshots=items))
    @typed_tool(mcp)
    @deterministic(input_model=TaxonomyInput, output_model=TaxonomyOutput)
    def metrics_get_by_taxonomy(domain: str | None = None, category: str | None = None, source_brick: str | None = None, input_tool: str | None = None, tags: list[str] | None = None) -> ToolResult[TaxonomyOutput]:
        definitions = [d for d in runtime.list_definitions() if (not domain or d.get("domain") == domain) and (not category or d.get("category") == category) and (not source_brick or d.get("source_brick") == source_brick) and (not input_tool or d.get("input_tool") == input_tool) and (not tags or set(tags).issubset(set(d.get("tags", []))))]
        return ok(TaxonomyOutput(ok=True, count=len(definitions), definitions=definitions))
    @typed_tool(mcp)
    @deterministic(input_model=CompareBaselineInput, output_model=BaselineComparisonOutput)
    def metrics_compare_baseline(metric_id: str, current_values: dict[str, float], baseline_tag: str, threshold_block: float = 0.05, threshold_warn: float = 0.02) -> ToolResult[BaselineComparisonOutput]:
        return ok(BaselineComparisonOutput.model_validate(runtime.compare_baseline(metric_id, current_values, baseline_tag, threshold_block, threshold_warn)))
    @typed_tool(mcp)
    @deterministic(input_model=ListBaselinesInput, output_model=BaselinesOutput)
    def metrics_list_baselines(metric_id: str | None = None) -> ToolResult[BaselinesOutput]:
        return ok(BaselinesOutput(baselines=runtime.list_baselines(metric_id)))
    @typed_tool(mcp)
    @deterministic(input_model=MeasureInput, output_model=MeasureOutput)
    def metrics_measure(focus: dict[str, JsonValue]) -> ToolResult[MeasureOutput]:
        return runtime.measure_focus(focus)
