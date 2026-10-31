"""UIView definitions for Sandbox brick — item_list layout.

Canvas handles chrome. Pure item_list component rendered
directly by ComponentTree, matching the evals pattern.

Thin assembler + registrar: individual view/component builders live in the
sibling ``views_*`` modules to keep every file under the 200-LOC ceiling.
"""

from __future__ import annotations

from typing import Any
from pydantic import Field

from factory.mcp_utils.interface import deterministic, ok
from factory.mcp_utils.runtime.tool_result import ToolResult
from ..runtime.runtime import SandboxRuntime
from .dashboard_summary import build_dashboard_summary
from .contracts import EmptyInput
from .view_models import (
    DashboardSummaryResult, EnvironmentActivityRequest,
    EnvironmentActivityResult, ViewsResult,
)
from .views_catalog import profiles_list, status_mix_chart
from .views_environments import environments_list
from .views_streams import activity_stream, graph_context_stream


def register(mcp: Any, runtime: SandboxRuntime) -> None:
    """Register Sandbox view definitions."""

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=DashboardSummaryResult)
    def sandbox_get_dashboard_summary() -> ToolResult[DashboardSummaryResult]:
        """Return aggregate sandbox dashboard data."""
        return ok(DashboardSummaryResult.model_validate(build_dashboard_summary(runtime)))

    @mcp.tool()
    @deterministic(input_model=EnvironmentActivityRequest, output_model=EnvironmentActivityResult)
    def sandbox_get_environment_activity(
        env_id: str = Field(min_length=1, max_length=256), limit: int = Field(default=20, ge=1, le=100),
    ) -> ToolResult[EnvironmentActivityResult]:
        """Return recent recorded activity for a specific environment."""
        from .dashboard_summary import list_recent_activity
        entries = list_recent_activity(limit=limit, env_id=env_id)
        return ok(EnvironmentActivityResult(env_id=env_id, entries=entries, count=len(entries)))

    @mcp.tool()
    @deterministic(input_model=EnvironmentActivityRequest, output_model=EnvironmentActivityResult)
    def sandbox_get_environment_graph_context(
        env_id: str = Field(min_length=1, max_length=256), limit: int = Field(default=12, ge=1, le=100),
    ) -> ToolResult[EnvironmentActivityResult]:
        """Return the sandbox graph entity plus nearby related entities."""
        from .dashboard_summary import list_related_graph_entities
        entries = list_related_graph_entities(limit=limit, env_id=env_id)
        return ok(EnvironmentActivityResult(env_id=env_id, entries=entries, count=len(entries)))

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ViewsResult)
    def sandbox_get_views() -> ToolResult[ViewsResult]:
        """Return UIView definitions for the Sandbox brick."""
        return ok(ViewsResult(views=[
            {
                "id": "sandbox-envs",
                "name": "Sandbox Environments",
                "brick": "sandbox",
                "icon": "📦",
                "layout": {"type": "flex", "direction": "column"},
                "components": [
                    status_mix_chart(),
                    environments_list(),
                    activity_stream(),
                    graph_context_stream(),
                    profiles_list(),
                ],
                "metadata": {
                    "description": "Sandbox fleet and target profile control surface",
                    "nav_label": "Sandbox",
                    "nav_order": 70,
                },
            },
        ]))
