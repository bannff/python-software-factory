"""Typed UI scenario management MCP tools."""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING
import uuid

from factory.mcp_utils.interface import ToolResult, deterministic, fail, operational

from .contracts.ui_explorer import (
    CreateUIScenarioInput, CreateUIScenarioOutput, ListUIScenariosInput,
    ListUIScenariosOutput, UIExplorerCapabilitiesInput,
    UIExplorerCapabilitiesOutput, UIScenarioIdInput, UIScenarioOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import EvalsRuntime


_ui_explorer: Any = None


def _get_explorer() -> Any:
    """Get or create the shared UI Explorer instance."""
    global _ui_explorer
    if _ui_explorer is None:
        from ..runtime.adapters import UIExplorerRunner
        _ui_explorer = UIExplorerRunner()
    return _ui_explorer


def register(mcp: Any, get_runtime: Callable[[], "EvalsRuntime"]) -> None:
    """Register UI scenario management tools with flat typed ingress."""

    @mcp.tool()
    @deterministic(
        input_model=UIExplorerCapabilitiesInput,
        output_model=UIExplorerCapabilitiesOutput,
    )
    def evals_ui_get_capabilities() -> ToolResult[UIExplorerCapabilitiesOutput]:
        """Get UI Explorer capabilities."""
        return UIExplorerCapabilitiesOutput(
            name="UI Explorer",
            description="Agentic UI testing via Chrome DevTools MCP",
            actions=["click", "fill", "hover", "wait", "navigate", "press_key"],
            assertions=["console_clean", "network_ok", "a11y_valid", "performance_budget"],
            reporters=["file", "console"],
            requires="chrome-devtools MCP server",
        )

    @mcp.tool()
    @operational(input_model=CreateUIScenarioInput, output_model=CreateUIScenarioOutput)
    def evals_create_ui_scenario(
        name: str, route: str, description: str = "", tags: list[str] | None = None,
    ) -> ToolResult[CreateUIScenarioOutput]:
        """Create a new UI exploration scenario."""
        from ..runtime.ui import UIScenario

        scenario = UIScenario(
            id=str(uuid.uuid4()), name=name, route=route,
            description=description, tags=tags or [],
        )
        _get_explorer().create_scenario(scenario)
        return CreateUIScenarioOutput(
            id=scenario.id, name=scenario.name, route=scenario.route,
            message="Scenario created. Add actions and assertions next.",
        )

    @mcp.tool()
    @deterministic(input_model=ListUIScenariosInput, output_model=ListUIScenariosOutput)
    def evals_list_ui_scenarios() -> ToolResult[ListUIScenariosOutput]:
        """List all registered UI scenarios."""
        scenarios = _get_explorer().list_scenarios()
        return ListUIScenariosOutput(
            scenarios=[UIScenarioOutput(**scenario.to_dict()) for scenario in scenarios],
            count=len(scenarios),
        )

    @mcp.tool()
    @deterministic(input_model=UIScenarioIdInput, output_model=UIScenarioOutput)
    def evals_get_ui_scenario(scenario_id: str) -> ToolResult[UIScenarioOutput]:
        """Get a UI scenario by ID."""
        scenario = _get_explorer().get_scenario(scenario_id)
        if scenario is None:
            return fail(f"Scenario not found: {scenario_id}")
        return UIScenarioOutput(**scenario.to_dict())
