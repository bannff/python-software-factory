"""Native MCP v2 surface for SDK-native paired tool-chaos evaluation."""
from __future__ import annotations

import time
import uuid
from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, operational

from ..runtime.ports import EvalAgentConfig, EvalCase, ExperimentConfig
from ..runtime.tool_chaos_contract import fault_conditions, selected_tools, validate_cases
from .simulation_contracts import ToolChaosInput, ToolChaosOutput
from .simulation_tools import _persist_request

if TYPE_CHECKING:
    from ..runtime.runtime import EvalsRuntime


def _cases(raw_cases: list[dict[str, Any]]) -> list[EvalCase]:
    return [
        EvalCase(
            id=str(case.get("id", f"case-{ordinal}")), name=str(case.get("name", f"case-{ordinal}")),
            input=case.get("input", ""), expected=case.get("expected_output"),
            metadata=case.get("metadata", {}),
        )
        for ordinal, case in enumerate(raw_cases)
    ]


def _request(report: Any, artifacts: dict[str, Any], run_id: str, model_id: str, tool_names: tuple[str, ...], duration_ms: float) -> dict[str, Any]:
    from ..runtime.run_record_contract import build_run_request
    return build_run_request(
        report, run_id,
        {"kind": "tool_chaos_prompt", "model_id": model_id, "tool_catalog": list(tool_names)},
        "tool_chaos", duration_ms, artifacts=artifacts,
    )


def _failure(error: str) -> ToolResult[ToolChaosOutput]:
    return ToolResult(ok=False, data=None, error=error)


def register(mcp: Any, get_runtime: Callable[[], "EvalsRuntime"]) -> None:
    """Register the separate, prompt-only native tool-chaos evaluator."""

    @mcp.tool()
    @operational(input_model=ToolChaosInput, output_model=ToolChaosOutput)
    def evals_run_tool_chaos(
        cases: list[dict[str, Any]], tool_names: list[str], faults: list[dict[str, Any]],
        evaluator_names: list[str] | None = None, rubric: str = "",
        model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        system_prompt: str = "You are a helpful assistant.", agent_id: str | None = None,
        experiment_name: str = "tool-chaos", run_id: str | None = None,
        persist_only: bool = False, record_run_request: dict[str, Any] | None = None,
    ) -> ToolResult[ToolChaosOutput]:
        """Run paired baseline/fault ToolSimulator chaos and persist one canonical record."""
        effective_run_id = run_id or f"tool-chaos-{uuid.uuid4().hex}"
        if persist_only:
            if not record_run_request or record_run_request.get("run_id") != effective_run_id:
                return _failure("persist_only requires the matching record_run_request")
            return ToolChaosOutput(
                run_id=effective_run_id, record_run_request=record_run_request,
                persistence=_persist_request(record_run_request),
            )
        if agent_id:
            return _failure("agent_id targets cannot attach ChaosPlugin on the registered-persona MCP route")
        try:
            validate_cases(cases)
            chosen_tools = selected_tools(tool_names)
            conditions = fault_conditions(faults, chosen_tools)
        except ValueError as exc:
            return _failure(str(exc))
        config = ExperimentConfig(
            cases=_cases(cases), evaluator_names=evaluator_names or ["output"], rubric=rubric,
            name=experiment_name, run_id=effective_run_id,
            agent_config=EvalAgentConfig(model_id=model_id, system_prompt=system_prompt),
        )
        started = time.perf_counter()
        try:
            from ..runtime.adapters.tool_chaos_adapter import run_tool_chaos
            report, artifacts = run_tool_chaos(config, chosen_tools, conditions)
        except Exception as exc:  # noqa: BLE001 - return stable run id for operator retry diagnosis
            return _failure(f"run_id={effective_run_id}: {exc}")
        request = _request(report, artifacts, effective_run_id, model_id, chosen_tools, (time.perf_counter() - started) * 1000)
        return ToolChaosOutput(
            run_id=effective_run_id, case_results=report.case_results, summary=report.summary,
            artifacts=artifacts, record_run_request=request, persistence=_persist_request(request),
        )
