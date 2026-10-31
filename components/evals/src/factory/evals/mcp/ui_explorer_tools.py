"""Typed UI Explorer execution MCP tools."""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, deterministic, fail, operational

from .contracts.ui_explorer import (
    AddScenarioActionInput, AddScenarioActionOutput, AddScenarioAssertionInput,
    AddScenarioAssertionOutput, ListUIFindingsOutput, RunUIExplorationInput,
    RunUIExplorationOutput, UIExplorationRunIdInput,
)
from .ui_scenario_tools import _get_explorer

if TYPE_CHECKING:
    from ..runtime.runtime import EvalsRuntime


def register(mcp: Any, get_runtime: Callable[[], "EvalsRuntime"]) -> None:
    """Register UI Explorer execution tools with flat typed ingress."""

    @mcp.tool()
    @operational(input_model=AddScenarioActionInput, output_model=AddScenarioActionOutput)
    def evals_add_scenario_action(
        scenario_id: str, action_type: str, target: str | None = None,
        value: str | None = None, timeout_ms: int = 5000,
    ) -> ToolResult[AddScenarioActionOutput]:
        """Add an action to a UI scenario."""
        from ..runtime.ui import Click, Fill, Hover, Navigate, PressKey, WaitFor

        scenario = _get_explorer().get_scenario(scenario_id)
        if scenario is None:
            return fail(f"Scenario not found: {scenario_id}")
        action_map = {
            "click": lambda: Click(target=target or "", timeout_ms=timeout_ms),
            "fill": lambda: Fill(target=target or "", value=value or "", timeout_ms=timeout_ms),
            "hover": lambda: Hover(target=target or "", timeout_ms=timeout_ms),
            "wait": lambda: WaitFor(text=value, timeout_ms=timeout_ms),
            "navigate": lambda: Navigate(url=value, timeout_ms=timeout_ms),
            "press_key": lambda: PressKey(key=value or "Enter", timeout_ms=timeout_ms),
        }
        if action_type not in action_map:
            return fail(f"Unknown action type: {action_type}")
        action = action_map[action_type]()
        scenario.actions.append(action)
        return AddScenarioActionOutput(
            scenario_id=scenario_id, action_added=action.to_dict(),
        )

    @mcp.tool()
    @operational(
        input_model=AddScenarioAssertionInput, output_model=AddScenarioAssertionOutput,
    )
    def evals_add_scenario_assertion(
        scenario_id: str, assertion_type: str, max_errors: int = 0,
        ignore_patterns: list[str] | None = None,
        allowed_failures: list[str] | None = None,
        required_landmarks: list[str] | None = None, lcp_ms: int = 2500,
        fid_ms: int = 100, cls: float = 0.1,
    ) -> ToolResult[AddScenarioAssertionOutput]:
        """Add an assertion to a UI scenario."""
        from ..runtime.ui import A11yValid, ConsoleClean, NetworkOK, PerformanceBudget

        scenario = _get_explorer().get_scenario(scenario_id)
        if scenario is None:
            return fail(f"Scenario not found: {scenario_id}")
        assertion_map = {
            "console_clean": lambda: ConsoleClean(
                max_errors=max_errors, ignore_patterns=ignore_patterns or [],
            ),
            "network_ok": lambda: NetworkOK(allowed_failures=allowed_failures or []),
            "a11y_valid": lambda: A11yValid(required_landmarks=required_landmarks or []),
            "performance_budget": lambda: PerformanceBudget(
                lcp_ms=lcp_ms, fid_ms=fid_ms, cls=cls,
            ),
        }
        if assertion_type not in assertion_map:
            return fail(f"Unknown assertion type: {assertion_type}")
        assertion = assertion_map[assertion_type]()
        scenario.assertions.append(assertion)
        return AddScenarioAssertionOutput(
            scenario_id=scenario_id, assertion_added=assertion.to_dict(),
        )

    @mcp.tool()
    @operational(input_model=RunUIExplorationInput, output_model=RunUIExplorationOutput)
    def evals_run_ui_exploration(
        scenario_id: str, context: dict[str, Any],
    ) -> ToolResult[RunUIExplorationOutput]:
        """Process collected UI context and run scenario assertions."""
        explorer = _get_explorer()
        try:
            run = explorer.run_scenario(scenario_id, context)
        except ValueError as error:
            return fail(str(error))
        findings = explorer.get_findings(run.id)
        return RunUIExplorationOutput(
            run_id=run.id, status=run.status, summary=run.summary,
            findings=[finding.to_dict() for finding in findings],
        )

    @mcp.tool()
    @deterministic(input_model=UIExplorationRunIdInput, output_model=ListUIFindingsOutput)
    def evals_list_ui_findings(run_id: str) -> ToolResult[ListUIFindingsOutput]:
        """Get findings from a UI exploration run."""
        findings = _get_explorer().get_findings(run_id)
        return ListUIFindingsOutput(
            run_id=run_id, findings=[finding.to_dict() for finding in findings],
            count=len(findings),
        )
