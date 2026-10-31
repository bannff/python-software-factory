"""Dispatch helpers — arg builders and side-effect persistence.

Private helpers split from ``dispatch.py`` so both files stay <200 LOC.
Pinned event types emitted (must remain literals): ``eval.completed``
from ``_persist_eval_result``; ``metrics.record`` from
``_build_metrics_payload``. Graph reads use the typed, polymorphic graph
tools from bd python-factory-j1lb (no raw Cypher) — see bd
python-factory-k1py / epic python-factory-kzd8.

Eval-side helpers (``_fetch_trace_summary``, ``_format_trace_row``,
``_persist_eval_result``) live in :mod:`_dispatch_evals` and are
re-exported here so test patch paths and ``dispatch.py`` imports keep
resolving.
"""

from __future__ import annotations

import logging
from typing import Any

from ._dispatch_evals import (  # noqa: F401 — re-exported for back-compat
    _fetch_trace_summary,
    _format_trace_row,
    _persist_eval_result,
)
from .models import Event
from .subscriptions import SubscriptionDefinition

logger = logging.getLogger(__name__)


def _build_args(
    tool_name: str, sub: SubscriptionDefinition,
    event: Event, invoker: Any,
) -> dict[str, Any]:
    """Build tool-specific args from event + subscription."""
    if tool_name == "events_publish":
        if sub.filters.get("event_type") == "metrics.record":
            return _build_metrics_payload(event, invoker)
        return {
            "event_type": sub.filters.get("event_type", "unknown"),
            "source": sub.filters.get("source", "events.dispatch"),
            "payload": event.payload,
        }
    if tool_name == "rewards_dispatch":
        return {}
    if tool_name in (
        "blockchain_reward_dispatch",
        "memory_learning_dispatch",
        "convergence_dispatch",
        "workflow_improvement_dispatch",
    ):
        return {}
    if tool_name in ("evals_evaluate_session", "evals_evaluate_multi"):
        run_id = event.payload.get("run_id", "")
        graph_id = event.payload.get("workflow_id") or event.payload.get("graph_id", "")
        trace = _fetch_trace_summary(run_id, invoker)
        return {
            "input_text": (
                f"Security workflow '{graph_id}' run_id={run_id}. "
                "Goal: find and prove vulnerabilities in the target app."
            ),
            "output_text": trace,
            "evaluator_names": ["faithfulness", "helpfulness"],
            "rubric": (
                "Score 1 if the agent executed real tool calls and "
                "produced grounded evidence. Score 0 if output appears "
                "fabricated or lacks tool traces."
            ),
        }
    return {"input_text": str(event.payload),
            "output_text": str(event.payload), **sub.filters}


def _build_metrics_payload(event: Event, invoker: Any) -> dict[str, Any]:
    """Compute real metrics from graph data via typed tools."""
    run_id = event.payload.get("run_id", "")
    exec_time = event.payload.get("execution_time", 0)
    workflow_id = event.payload.get("workflow_id") or event.payload.get("graph_id", "")
    # bd:python-factory-2sjyz — let the event payload drive the label set
    # so domain agents (wine, workout, ...) bucket their own findings.
    count_labels = event.payload.get("count_labels") or None
    finding_cnt = _count_findings(invoker, run_id, count_labels=count_labels)
    tool_calls, tool_ok, tool_avg_ms = _tool_invocation_stats(invoker, run_id)
    error_rate = 1 - (tool_ok / tool_calls) if tool_calls > 0 else 0
    return {
        "event_type": "metrics.record",
        "source": "events.auto-metrics",
        "payload": {
            "run_id": run_id, "graph_id": workflow_id,
            "workflow_id": workflow_id,
            "execution_time_s": exec_time,
            "findings_count": finding_cnt,
            "tool_calls": tool_calls,
            "tool_error_rate": round(error_rate, 3),
            "tool_avg_latency_ms": round(tool_avg_ms, 1),
            "cycle_efficiency": round(finding_cnt / max(tool_calls, 1), 3),
            # bd:hv5rv — carry domain so the telemetry reward source can tag
            # its cautionary learning {domain}-learnings for per-agent recall.
            "domain_class": (
                event.payload.get("domain_class")
                or event.payload.get("vuln_class", "")
            ),
        },
    }


def _count_findings(
    invoker: Any, run_id: str,
    count_labels: list[str] | None = None,
) -> int:
    """Count entities for a run.

    Defaults to ``("Finding", "ProvenExploit")`` for back-compat
    (bd:python-factory-2sjyz). Domain agents pass ``count_labels=[...]``
    from the event payload's ``count_labels`` field to override.
    """
    if not run_id:
        return 0
    labels = list(count_labels) if count_labels else ["Finding", "ProvenExploit"]
    try:
        result = invoker(
            "graph_count_entities_by_run", run_id=run_id, labels=labels,
        )
    except Exception:
        return 0
    counts = result.data.counts if result.ok and result.data is not None else {}
    try:
        return sum(int(counts.get(label, 0)) for label in labels)
    except (TypeError, ValueError):
        return 0


def _tool_invocation_stats(invoker: Any, run_id: str) -> tuple[int, int, float]:
    """Return ``(calls, ok, avg_latency_ms)`` from typed graph tool."""
    if not run_id:
        return 0, 0, 0.0
    try:
        result = invoker(
            "graph_get_tool_invocations_for_run", run_id=run_id, limit=10_000,
        )
    except Exception:
        return 0, 0, 0.0
    rows = result.data.rows if result.ok and result.data is not None else []
    if not rows:
        return 0, 0, 0.0
    calls = len(rows)
    ok = sum(1 for r in rows if r.get("success"))
    total_ms = 0.0
    for row in rows:
        try:
            total_ms += float(row.get("latency_ms") or 0)
        except (TypeError, ValueError):
            pass
    return calls, ok, total_ms / calls
