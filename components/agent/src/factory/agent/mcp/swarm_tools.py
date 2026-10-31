"""MCP tools for swarm execution with session capture.

Exposes run_swarm_eval — runs a registered swarm against a target
directory and returns results with a Strands Session for full
evaluator coverage (OUTPUT, TRACE, and SESSION level).
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from factory.mcp_utils.interface import operational

if TYPE_CHECKING:
    from ..agent import SuperAgent


def register(mcp: Any, agent: "SuperAgent") -> None:
    """Register swarm execution tools."""

    @mcp.tool()
    @operational
    def run_swarm_eval(
        swarm_id: str,
        target_dir: str,
        prompt: str = "",
        run_id: str = "",
    ) -> dict[str, Any]:
        """Run a registered swarm with session capture for evals.

        Executes the swarm against target_dir, captures real OTEL spans
        via the telemetry brick's StrandsCapture adapter, and returns
        a Strands Session object directly. The returned session can be
        passed to evals_evaluate_session for full coverage including
        SESSION_LEVEL evaluators (trajectory, interactions, goal_success).

        Args:
            swarm_id: ID of a registered swarm (from get_swarm_registry).
            target_dir: Absolute path to directory to scan.
            prompt: Task prompt. If empty, uses a default security review
                prompt for the target directory.
            run_id: Optional run identifier (auto-generated if empty).

        Returns:
            Dict with: status, run_id, output (report text), trajectory,
            per_node_metrics, token_usage, execution_time_ms, wall_time_s,
            iterations, report_length, session, span_count.
        """
        if not agent.swarm_registry:
            return {"status": "error", "output": "No swarm registry"}

        config = agent.swarm_registry.get(swarm_id)
        if not config:
            available = [s["id"] for s in agent.swarm_registry.list_swarms()]
            return {
                "status": "error",
                "output": f"Swarm '{swarm_id}' not found. Available: {available}",
            }

        if not prompt:
            prompt = (
                f"Perform a comprehensive security review of the code in: "
                f"{target_dir}\n\nThis is a Python component/module. Read all "
                f"source files, trace data flows, identify vulnerabilities, "
                f"and produce a structured security assessment report with "
                f"STRIDE categorization and DREAD scoring."
            )

        from ..runtime.adapters.swarm_runner import run_swarm_with_session

        return run_swarm_with_session(
            config=config,
            target_dir=target_dir,
            prompt=prompt,
            run_id=run_id,
        )
