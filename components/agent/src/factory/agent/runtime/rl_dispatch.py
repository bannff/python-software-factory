"""RL loop dispatch — triggers reward processing after graph completion.

Extracted from mcp/async_tools.py to keep that file under 200 LOC.
``domain_class`` is read from ctx with ``vuln_class`` fallback per the
meta-architect Q4 dual-emit verdict on epic python-factory-hadbi
(bd:python-factory-tmlrx). Both fields forward into
``games_process_workflow_rl`` so security recipes that key off
``vuln_class`` and domain-agnostic recipes that key off ``domain_class``
both produce useful RL events / memory tags.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def run_rl_loop(graph_id: str, ctx: dict[str, Any]) -> None:
    """Trigger the RL loop after a graph completes. Fire-and-forget."""
    try:
        from factory.mcp_utils.interface import get_service
        invoker = get_service("tool_invoker")
        if not invoker:
            return
        run_id = ctx.get("run_id", "")
        vuln_class = ctx.get("vuln_class", "")
        # bd:python-factory-twxj0 — coalesce so domain agents that only set
        # ``domain_class`` and security agents that only set ``vuln_class``
        # both reach the games engine with both fields populated.
        domain_class = ctx.get("domain_class", "") or vuln_class
        target_app = ctx.get("target_app", "")
        count_labels = ctx.get("count_labels")
        match_on = ctx.get("match_on")
        result = invoker(
            "games_process_workflow_rl",
            graph_id=graph_id, run_id=run_id,
            vuln_class=vuln_class, domain_class=domain_class,
            target_app=target_app,
            count_labels=[count_labels] if isinstance(count_labels, str) else count_labels,
            match_on=match_on,
        )
        logger.info("RL loop completed for %s: %s", run_id, result)
        # Write experiment report (fire-and-forget)
        try:
            invoker(
                "games_write_experiment_report",
                run_id=run_id, workflow_type="strands",
                target_app=target_app, vuln_class=vuln_class,
                domain_class=domain_class,
                framework="", agent_count=0, duration_seconds=0,
            )
        except Exception:
            pass  # Don't fail the RL loop if report writing fails
    except Exception as e:
        logger.warning("RL loop failed for %s: %s", graph_id, e)
