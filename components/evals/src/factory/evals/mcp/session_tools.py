"""Typed MCP tool for evaluation with normalized session evidence."""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, fail, operational

from .evaluator_session_contracts import EvaluateMultiOutput, EvaluateSessionInput

if TYPE_CHECKING:
    from ..runtime.runtime import EvalsRuntime


def register(mcp: Any, get_runtime: Callable[[], "EvalsRuntime"]) -> None:
    """Register session-based evaluation tools."""

    @mcp.tool()
    @operational(input_model=EvaluateSessionInput, output_model=EvaluateMultiOutput)
    def evals_evaluate_session(
        input_text: str, output_text: str, evaluator_names: list[str],
        session_data: dict[str, Any] | None = None,
        otel_spans_json: list[str] | None = None, session: Any | None = None,
        rubric: str = "", expected_output: str | None = None,
        actual_interactions: list[dict[str, Any]] | None = None,
    ) -> ToolResult[EvaluateMultiOutput]:
        """Run session-aware evaluators; evaluator failures remain result rows."""
        try:
            value = get_runtime().evaluate_with_real_session(
                input_text, output_text, evaluator_names,
                session_data=session_data, otel_spans_json=otel_spans_json,
                session=session, rubric=rubric, expected_output=expected_output,
                actual_interactions=actual_interactions,
            )
        except (RuntimeError, ValueError) as error:
            return fail(str(error))
        return fail(value["error"]) if "error" in value else EvaluateMultiOutput(**value)
