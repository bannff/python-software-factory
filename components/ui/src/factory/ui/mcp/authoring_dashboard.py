"""Typed dashboard creation authoring tool for the UI module."""

from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING, cast

from factory.mcp_utils.interface import ToolResult, authoring, fail, ok

from .authoring_dtos import CreateDashboardInput, CreateDashboardOutput

if TYPE_CHECKING:
    from ..runtime.envelope import ContextEnvelope
    from ..runtime.runtime import UIRuntime


def register(
    mcp: Any,
    get_runtime: Callable[[], "UIRuntime"],
    parse_envelope: Callable[[dict[str, Any] | None], "ContextEnvelope"],
    is_authoring_enabled: Callable[[], bool],
) -> None:
    """Register the security-gated typed dashboard creation tool."""

    @mcp.tool()
    @authoring(input_model=CreateDashboardInput, output_model=CreateDashboardOutput)
    async def ui_create_dashboard(
        name: str,
        metrics: list[dict[str, Any]] | None = None,
        charts: list[dict[str, Any]] | None = None,
        tables: list[dict[str, Any]] | None = None,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[CreateDashboardOutput]:
        """Create a complete dashboard with metrics, charts, and tables."""
        from ..runtime.models import ComponentType

        ctx = parse_envelope(envelope)
        if not is_authoring_enabled():
            return cast(ToolResult[CreateDashboardOutput], fail("Authoring tools disabled"))

        runtime = get_runtime()
        view = runtime.view_manager.create_view(
            name=name, layout={"type": "grid", "columns": 3}
        )
        for props in metrics or []:
            component = runtime.view_manager.create_component(ComponentType.METRIC, props=props)
            await runtime.view_manager.add_component(view.id, component)
        for props in charts or []:
            component = runtime.view_manager.create_component(ComponentType.CHART, props=props)
            await runtime.view_manager.add_component(view.id, component)
        for props in tables or []:
            component = runtime.view_manager.create_component(ComponentType.TABLE, props=props)
            await runtime.view_manager.add_component(view.id, component)

        return ok(CreateDashboardOutput(created=True, view_id=view.id, request_id=ctx.request_id))
