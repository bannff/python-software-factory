"""Eval dispatch helpers: durable Evals writes precede graph/event projections."""
from __future__ import annotations

import logging
import math
import os
from typing import Any

from .mcp_result import successful_data

logger = logging.getLogger(__name__)

# Summary divergence tolerance: caller-vs-rows aggregates differing by more than
# this are surfaced (observability only; rows-derived values stay authoritative).
_SUMMARY_EPSILON = 0.01


def _resolve_pass_threshold() -> float:
    """Read the fallback pass threshold once from env, guarding bad values.

    Non-float or non-positive settings fall back to 1.0 so the default remains
    byte-identical unless a valid override is supplied.
    """
    try:
        threshold = float(os.getenv("COMPANION_X_EVAL_PASS_THRESHOLD", "1.0"))
    except (TypeError, ValueError):
        return 1.0
    if not math.isfinite(threshold) or threshold <= 0:
        return 1.0
    return threshold


_PASS_THRESHOLD = _resolve_pass_threshold()


def _fetch_trace_summary(run_id: str, invoker: Any) -> str:
    """Fetch a typed graph tool trace for a run."""
    if not run_id:
        return "No run_id available; trace not scoped"
    try:
        result = invoker("graph_get_tool_invocations_for_run", run_id=run_id, limit=50)
        rows = result.data.rows if result.ok and result.data is not None else []
        if not rows:
            return f"No tool trace found for run {run_id}"
        return f"Tool trace ({len(rows)} calls):\n" + "\n".join(_format_trace_row(row) for row in rows)
    except Exception as exc:
        return f"Trace fetch failed: {exc}"


def _format_trace_row(row: dict[str, Any]) -> str:
    """Render one ToolInvocation row."""
    tool = row.get("tool_name") or row.get("tool") or "?"
    ok = row.get("success") if "success" in row else row.get("ok")
    try:
        milliseconds = float(row.get("latency_ms", row.get("ms", 0)) or 0)
    except (TypeError, ValueError):
        milliseconds = 0.0
    return f"{tool} ok={ok} {milliseconds:.0f}ms"

def _persist_eval_result(invoker: Any, payload: dict[str, Any], result: Any) -> None:
    """Commit canonical evidence, then independently project its pointer."""
    result = successful_data(result) or {}
    run_id = payload.get("run_id", "unknown")
    graph_id = payload.get("workflow_id") or payload.get("graph_id", "unknown")
    summary = result.get("summary", {}) if isinstance(result, dict) else {}
    durable = _bridge_auto_eval_to_evals(invoker, run_id, graph_id, summary, result)
    projection = _projection_payload(durable, run_id, graph_id, summary)
    if projection is None:
        logger.warning("auto-eval durable write skipped projections: %s", durable)
        return
    # S4b eval-gated payout — the eval_results projection is the release gate.
    # Evidence is durably committed above, so any reward escrowed for this
    # run_id may now be credited (idempotent, once per run).
    from .eval_payout import release_eval_gated_reward
    release_eval_gated_reward(invoker, run_id)
    try:
        invoker("events_publish", event_type="eval.completed", source="events.auto-eval",
                payload=projection)
    except Exception as exc:
        logger.warning("eval lifecycle projection failed: %s", exc)
    try:
        invoker(
            "graph_add_entity", entity_id=f"eval-record-{projection['pointer']['doc_id']}",
            entity_type="EvalRecordPointer", properties=projection,
        )
    except Exception as exc:
        logger.warning("eval graph projection failed: %s", exc)

def _durable_data(response: Any) -> dict[str, Any]:
    data = successful_data(response)
    if data is None:
        return {
            "persisted": False,
            "reason": getattr(response, "error", None) or "durable write failed",
        }
    return data

def _projection_payload(durable: dict[str, Any], run_id: str, graph_id: str, summary: dict[str, Any]) -> dict[str, Any] | None:
    """Build a pointer-only projection after a successful immutable commit."""
    pointer = durable.get("pointer")
    key = durable.get("projection_key")
    if not durable.get("persisted") or not isinstance(pointer, dict) or not key:
        return None
    return {
        "pointer": pointer,
        "projection_key": key,
        "run_id": run_id,
        "workflow_id": graph_id,
        "summary": {
            "avg_score": summary.get("avg_score", 0),
            "pass_rate": summary.get("pass_rate", 0),
        },
    }


def _normalize_case(row: Any) -> tuple[dict[str, Any], float, bool]:
    """Normalize a raw auto-eval case and derive its pass state."""
    case = dict(row) if isinstance(row, dict) else {}
    try:
        score = float(case.get("score", 0.0) or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    if not math.isfinite(score):
        score = 0.0
    score = min(1.0, max(0.0, score))
    raw_passed = case.get("passed")
    passed = raw_passed if isinstance(raw_passed, bool) else score >= _PASS_THRESHOLD
    case["score"] = score
    case["passed"] = passed
    return case, score, passed


def _warn_on_summary_divergence(
    run_id: str, base_summary: dict[str, Any], pass_rate: float, avg_score: float,
) -> None:
    """Log when caller-supplied aggregates materially differ from rows-derived ones.

    Observability only: rows-derived aggregates stay authoritative and the write
    is never failed or skipped on divergence.
    """
    for key, derived in (("pass_rate", pass_rate), ("avg_score", avg_score)):
        raw = base_summary.get(key)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            continue
        caller = float(raw)
        if not math.isfinite(caller):
            continue
        if abs(caller - derived) > _SUMMARY_EPSILON:
            logger.warning(
                "auto-eval summary divergence for run %s: caller %s=%s vs rows-derived %s=%s",
                run_id, key, caller, key, derived,
            )


def _bridge_auto_eval_to_evals(invoker: Any, run_id: str, graph_id: str, summary: dict[str, Any], result: Any | None = None) -> dict[str, Any]:
    """Write normalized auto-eval evidence through Evals' immutable writer."""
    if not run_id or run_id == "unknown":
        return {"persisted": False, "reason": "empty run_id"}
    rows = result.get("results", []) if isinstance(result, dict) else []
    if not rows:
        return {"persisted": False, "reason": "no case results to record"}
    try:
        cases: list[dict[str, Any]] = []
        scores: list[float] = []
        passed_flags: list[bool] = []
        for row in rows:
            case, score, passed = _normalize_case(row)
            cases.append(case)
            scores.append(score)
            passed_flags.append(passed)
        total = len(cases)
        passed = sum(passed_flags)
        failed = total - passed
        pass_rate = passed / total
        avg_score = sum(scores) / total
        base_summary = summary if isinstance(summary, dict) else {}
        _warn_on_summary_divergence(run_id, base_summary, pass_rate, avg_score)
        consistent_summary = {
            **base_summary,
            "total_cases": total, "passed": passed, "passed_cases": passed,
            "failed": failed, "failed_cases": failed,
            "pass_rate": pass_rate, "avg_score": avg_score, "overall_score": avg_score,
        }
        response = invoker(
            "evals_record_run", run_id=run_id, experiment_name=f"auto-eval:{graph_id}",
            verdict="PASS" if passed == total else "FAIL", pass_rate=round(pass_rate, 3),
            avg_score=round(avg_score, 3), total_cases=total, passed=passed,
            failed_cases=failed, case_results=cases, case_scores=scores,
            evaluators_used=[case.get("evaluator", "") for case in cases],
            agent={}, source="auto-eval", summary=consistent_summary,
        )
        return _durable_data(response)
    except Exception as exc:
        logger.warning("auto-eval durable write failed: %s", exc)
        return {"persisted": False, "reason": str(exc)}
