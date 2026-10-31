"""Typed deterministic Bayesian statistics tools for Metrics."""
from __future__ import annotations

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic, ok
from factory.mcp_utils.registration import typed_tool

from .contracts.deterministic import (
    IterationEfficiencyInput, IterationEfficiencyOutput, PrecisionInput,
    PrecisionOutput, SampleSizeInput, SampleSizeOutput,
)


def _result(value: dict[str, Any], model: type[Any]) -> ToolResult[Any]:
    return ok(model.model_validate(value))


def register(mcp: Any, runtime: Any) -> None:
    """Register pure Bayesian estimation tools with strict flat ingress."""

    @typed_tool(mcp)
    @deterministic(input_model=PrecisionInput, output_model=PrecisionOutput)
    def metrics_precision_estimate(reviewed: int, true_positives: int, prior_a: float = 1.0, prior_b: float = 1.0, target_precision: float = 0.10) -> ToolResult[PrecisionOutput]:
        from ..runtime.bayesian import precision_estimate
        return _result(precision_estimate(reviewed, true_positives, prior_a, prior_b, target_precision), PrecisionOutput)

    @typed_tool(mcp)
    @deterministic(input_model=SampleSizeInput, output_model=SampleSizeOutput)
    def metrics_sample_size(estimated_precision: float = 0.0196, confidence: float = 0.95, min_true_positives: int = 1) -> ToolResult[SampleSizeOutput]:
        from ..runtime.bayesian import sample_size
        return _result(sample_size(estimated_precision, confidence, min_true_positives), SampleSizeOutput)

    @typed_tool(mcp)
    @deterministic(input_model=IterationEfficiencyInput, output_model=IterationEfficiencyOutput)
    def metrics_iteration_efficiency(initial_ratio: float = 50.0, budget: int = 5000, sample_size: int = 200, improvement_rate: float = 0.95) -> ToolResult[IterationEfficiencyOutput]:
        from ..runtime.bayesian import iteration_efficiency
        return _result(iteration_efficiency(initial_ratio, budget, sample_size, improvement_rate), IterationEfficiencyOutput)
