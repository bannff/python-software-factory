"""Typed MCP tools for the Evals SOP lifecycle."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic, fail, operational

from .contracts.deterministic import EmptyInput
from .contracts.sop import (
    SopGenerateDataInput, SopGenerateDataOutput, SopListOutput, SopPlanInput,
    SopPlanOutput, SopReportOutput, SopRunInput, SopRunOutput, SopSessionIdInput,
    SopStatusOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import EvalsRuntime


def _output(result: dict, output_type):
    return fail(result["error"]) if "error" in result else output_type(**result)


def register(mcp: Any, get_runtime: Callable[[], "EvalsRuntime"]) -> None:
    """Register the four-phase SOP lifecycle and its read projections."""

    @mcp.tool()
    @operational(input_model=SopPlanInput, output_model=SopPlanOutput)
    def evals_sop_plan(
        agent_description: str, agent_tools: list[str] | None = None,
        evaluation_goals: str = "",
    ) -> ToolResult[SopPlanOutput]:
        """Phase 1: create an evaluation plan for an agent."""
        return SopPlanOutput(**get_runtime().create_sop_session(
            agent_description, agent_tools, evaluation_goals,
        ))

    @mcp.tool()
    @operational(input_model=SopGenerateDataInput, output_model=SopGenerateDataOutput)
    def evals_sop_generate_data(
        session_id: str, num_cases: int = 10, evaluator_name: str = "output",
    ) -> ToolResult[SopGenerateDataOutput]:
        """Phase 2: generate test cases for a planned SOP session."""
        return _output(get_runtime().generate_sop_test_data(
            session_id, num_cases, evaluator_name,
        ), SopGenerateDataOutput)

    @mcp.tool()
    @operational(input_model=SopRunInput, output_model=SopRunOutput)
    def evals_sop_run(
        session_id: str,
        model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        system_prompt: str = "", evaluator_names: list[str] | None = None,
        rubric: str = "",
    ) -> ToolResult[SopRunOutput]:
        """Phase 3: execute the planned evaluation."""
        return _output(get_runtime().run_sop_evaluation(
            session_id, model_id=model_id, system_prompt=system_prompt,
            evaluator_names=evaluator_names, rubric=rubric,
        ), SopRunOutput)

    @mcp.tool()
    @operational(input_model=SopSessionIdInput, output_model=SopReportOutput)
    def evals_sop_report(session_id: str) -> ToolResult[SopReportOutput]:
        """Phase 4: produce a report for a completed SOP evaluation."""
        return _output(get_runtime().generate_sop_report(session_id), SopReportOutput)

    @mcp.tool()
    @deterministic(input_model=SopSessionIdInput, output_model=SopStatusOutput)
    def evals_sop_status(session_id: str) -> ToolResult[SopStatusOutput]:
        """Return the current SOP session state."""
        return SopStatusOutput(**get_runtime().get_sop_session(session_id))

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=SopListOutput)
    def evals_sop_list() -> ToolResult[SopListOutput]:
        """List all persisted SOP sessions."""
        sessions = get_runtime().list_sop_sessions()
        return SopListOutput(sessions=sessions, count=len(sessions))
