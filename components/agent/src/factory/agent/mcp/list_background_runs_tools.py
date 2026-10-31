"""List background subagent / loop-cycle Workflow runs (row 80 rail badge)."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from factory.mcp_utils.interface import (
    ToolResult, deterministic, fail, get_envelope, normalize_envelope, ok,
)

from .contracts.list_background_runs import (
    BackgroundRunView, ListBackgroundRunsInput, ListBackgroundRunsOutput,
)
from ..runtime.background.list_runs import BackgroundListError, list_background_runs

if TYPE_CHECKING:
    from ..agent import SuperAgent


def register(mcp: Any, agent: "SuperAgent") -> None:
    @mcp.tool(name="agent.list_background_runs")
    @deterministic(
        input_model=ListBackgroundRunsInput, output_model=ListBackgroundRunsOutput,
    )
    async def list_background_runs_tool(
        origin_thread_id: str | None = None, active_only: bool = False,
        limit: int = 50,
    ) -> ToolResult[ListBackgroundRunsOutput]:
        """Background spawns/loop-cycles as Workflow runs, filtered by origin thread."""
        envelope = normalize_envelope(get_envelope())
        try:
            rows = await list_background_runs(envelope, origin_thread_id, active_only, limit)
        except BackgroundListError as exc:
            return fail(exc.code)
        return ok(ListBackgroundRunsOutput(
            runs=[BackgroundRunView.model_validate(row) for row in rows],
        ))


__all__ = ["register"]
