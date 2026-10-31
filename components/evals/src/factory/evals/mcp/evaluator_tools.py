"""Typed MCP tools for framework-neutral evaluator and CAN invocation."""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, deterministic, fail, operational

from .evaluator_session_contracts import (
    CanMetricsOutput, CanModelEvidenceOutput, CanModelInput, ComputationalInput,
    ComputationalOutput, EvaluateInput, EvaluateMultiInput, EvaluateMultiOutput,
    EvaluateOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import EvalsRuntime


def _result(value: dict[str, Any], output: type[ToolResult]) -> ToolResult:
    return fail(value["error"]) if "error" in value else output(**value)


def register(mcp: Any, get_runtime: Callable[[], "EvalsRuntime"]) -> None:
    """Register direct evaluator tools."""

    @mcp.tool()
    @operational(input_model=EvaluateInput, output_model=EvaluateOutput)
    def evals_evaluate(
        input_text: str, output_text: str, evaluator_name: str = "non_empty",
        rubric: str = "", expected_output: str | None = None,
        framework: str = "deterministic",
    ) -> ToolResult[EvaluateOutput]:
        """Run one evaluator from the selected framework over input and output."""
        try:
            value = get_runtime().evaluate_output(
                input_text, output_text, evaluator_name, rubric,
                expected_output, framework,
            )
        except (RuntimeError, ValueError) as error:
            return fail(str(error))
        return _result(value, EvaluateOutput)

    @mcp.tool()
    @operational(input_model=EvaluateMultiInput, output_model=EvaluateMultiOutput)
    def evals_evaluate_multi(
        input_text: str, output_text: str, evaluator_names: list[str],
        rubric: str = "", expected_output: str | None = None,
        framework: str = "deterministic",
        actual_trajectory: list[Any] | None = None,
        expected_trajectory: list[Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> ToolResult[EvaluateMultiOutput]:
        """Run multiple evaluators from a framework; errors remain result rows."""
        try:
            value = get_runtime().evaluate_output_multi(
                input_text, output_text, evaluator_names, rubric,
                expected_output, framework,
                actual_trajectory=actual_trajectory,
                expected_trajectory=expected_trajectory, options=options,
            )
        except (RuntimeError, ValueError) as error:
            return fail(str(error))
        return _result(value, EvaluateMultiOutput)

    @mcp.tool()
    @deterministic(input_model=ComputationalInput, output_model=ComputationalOutput)
    def evals_evaluate_computational(
        evaluator_name: str, y_true: list, y_pred: list, scores: list,
    ) -> ToolResult[ComputationalOutput]:
        """Run one registered computational evaluator on pre-computed arrays."""
        from ..runtime.adapters.computational_evaluators import (
            COMPUTATIONAL_EVALUATORS, run_computational,
        )
        if evaluator_name not in COMPUTATIONAL_EVALUATORS:
            return fail(f"Unknown computational evaluator: {evaluator_name}")
        try:
            return ComputationalOutput(**run_computational(
                evaluator_name, y_true, y_pred, scores,
            ))
        except ValueError as error:
            return fail(str(error))

    @mcp.tool()
    @deterministic(input_model=CanModelInput, output_model=CanMetricsOutput)
    def evals_evaluate_can_model(
        y_true: list, y_pred: list, y_score: list | None = None,
    ) -> ToolResult[CanMetricsOutput]:
        """Run the CAN metrics bundle."""
        from ..runtime.adapters.can_evaluator import evaluate_can_model
        try:
            return CanMetricsOutput(**evaluate_can_model(y_true, y_pred, y_score))
        except ValueError as error:
            return fail(str(error))

    @mcp.tool()
    @deterministic(input_model=CanModelInput, output_model=CanModelEvidenceOutput)
    def evals_evaluate_can_model_evidence(
        y_true: list, y_pred: list, y_score: list | None = None,
    ) -> ToolResult[CanModelEvidenceOutput]:
        """Return versioned CAN metrics with Evals-owned input provenance."""
        from ..runtime.adapters.can_evaluator import evaluate_can_model_evidence
        try:
            return CanModelEvidenceOutput(**evaluate_can_model_evidence(
                y_true, y_pred, y_score,
            ))
        except ValueError as error:
            return fail(str(error))
