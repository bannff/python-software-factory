"""Operational (stateful) MCP tools for the learning brick.

``learning_compute_reward`` is the neutral reward entry point: it iterates
all registered reward sources for a completed run and returns the winning
neutral signal plus bounded source evidence. The events ``rewards_handler``
calls this INSTEAD of ``games_process_workflow_rl`` directly. The built-in
sources are ``gt-findings``, ``llm-judge``, ``user-feedback``, and
``telemetry``; only the GT source delegates to Games. No cross-brick imports —
sources reach other bricks through the MCP invoker.
"""

from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.decorators import operational
from factory.mcp_utils.registration import typed_tool
from factory.mcp_utils.runtime.tool_result import ToolResult, ok

from .contracts import ComputeRewardInput, ComputeRewardOutput

if TYPE_CHECKING:
    from ..runtime.runtime import LearningRuntime


def _invoker() -> Callable[..., Any] | None:
    """Return the cross-brick MCP tool invoker, or None if unavailable."""
    try:
        from factory.mcp_utils.interface import get_service
        return get_service("tool_invoker")
    except Exception:
        return None


def register(mcp: Any, get_runtime: Callable[[], "LearningRuntime"]) -> None:
    """Register operational tools with the Learning MCP server."""

    @typed_tool(mcp)
    @operational(input_model=ComputeRewardInput, output_model=ComputeRewardOutput)
    def learning_compute_reward(
        graph_id: str = "",
        run_id: str = "",
        vuln_class: str = "",
        domain_class: str = "",
        workflow_type: str = "auto",
        target_app: str = "",
        input_summary: str = "",
        output_summary: str = "",
        feedback_verdict: str = "",
        tool_error_rate: float | None = None,
    ) -> ToolResult[ComputeRewardOutput]:
        """Compute a neutral reward using the existing flat defaults.

        Strict ingress rejects coercion and unknown kwargs. The successful
        result is always ``ToolResult[ComputeRewardOutput]``; source evidence
        is normalized to bounded JSON before it crosses the MCP boundary.
        """
        run_ctx = {
            "graph_id": graph_id,
            "run_id": run_id,
            "vuln_class": vuln_class,
            # Coalesce so security recipes (vuln_class) and domain agents
            # (domain_class) both populate the neutral context.
            "domain_class": domain_class or vuln_class,
            "workflow_type": workflow_type,
            "target_app": target_app,
            # Work-output context for non-finding sources (llm-judge).
            "input_summary": input_summary,
            "output_summary": output_summary,
            # Explicit signal for the user-feedback source.
            "feedback_verdict": feedback_verdict,
            # Process-health signal for the telemetry source.
            "tool_error_rate": tool_error_rate,
        }
        return ok(ComputeRewardOutput(**get_runtime().compute(run_ctx, _invoker())))
