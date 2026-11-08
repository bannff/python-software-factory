"""Eval-freshness staleness handler (bd:python-factory-v7imt.4).

Shared handler for two convergence triggers:
1. ON-COMPLETION: graph.completed / swarm.completed events
2. CADENCE: eval.freshness.due events from AgentRunner timer

Logic: check the target experiment's last-eval timestamp vs a
configurable staleness threshold.  If stale, persist a freshness
eval via the evals brick's evals_persist_score MCP tool (lookup uses evals_list_run_results) (through
invoker — no cross-brick imports).

Defensive: failures are logged and reported in the returned summary but
NEVER break the caller's completion or timer path.  A failed freshness
lookup yields ``action="error"`` (not "stale") and persists nothing.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import Any

from .mcp_result import successful_data

from .models import Event

logger = logging.getLogger(__name__)

# Default staleness threshold: 1 hour (3600s).  Injected via
# FRESHNESS_STALENESS_THRESHOLD_S env var for configurability.
_DEFAULT_STALENESS_THRESHOLD_S = 3600


def _get_staleness_threshold() -> float:
    """Read staleness threshold from env, falling back to default."""
    raw = os.environ.get("FRESHNESS_STALENESS_THRESHOLD_S")
    if raw is not None:
        try:
            val = float(raw)
            if val > 0:
                return val
        except (TypeError, ValueError):
            pass
    return float(_DEFAULT_STALENESS_THRESHOLD_S)


class FreshnessLookupError(RuntimeError):
    """The evals lookup failed or returned an unusable shape.

    Distinct from "never evaluated": a failed lookup says nothing about
    freshness, so the handler must report it instead of guessing stale.
    """


def _parse_run_timestamp(raw: Any) -> float:
    """Parse an RFC3339 run timestamp (``...Z``) into epoch seconds."""
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
    except ValueError as exc:
        raise FreshnessLookupError(f"unparseable run timestamp {raw!r}") from exc


def _matches_target(experiment_name: Any, target: str) -> bool:
    # Score records are named ``score:<workflow_type>:<target_app>``.
    name = str(experiment_name)
    return name == target or name.endswith(f":{target}")


def _get_last_eval_timestamp(invoker: Any, run_id: str, target_app: str) -> float | None:
    """Newest persisted eval run for this target, via ``evals_list_run_results``.

    Returns epoch seconds, or None if the target was never evaluated.
    Raises FreshnessLookupError when the lookup itself fails.
    """
    target = target_app or run_id
    result = invoker("evals_list_run_results")
    data = successful_data(result)
    if data is None:
        raise FreshnessLookupError(f"evals_list_run_results failed: {result!r}")
    runs = data.get("runs")
    if not isinstance(runs, list):
        raise FreshnessLookupError("evals_list_run_results returned no 'runs' list")
    stamps = [
        _parse_run_timestamp(run["timestamp"])
        for run in runs
        if isinstance(run, dict)
        and run.get("timestamp") is not None
        and _matches_target(run.get("experiment_name", ""), target)
    ]
    return max(stamps, default=None)


def _is_stale(last_eval_ts: float | None, threshold_s: float) -> bool:
    """Determine if an experiment is stale (no recent eval)."""
    if last_eval_ts is None:
        # Never evaluated → stale
        return True
    age = time.time() - last_eval_ts
    return age > threshold_s


def _persist_freshness_eval(invoker: Any, event: Event) -> None:
    """Persist a freshness eval via evals_persist_score. Best-effort."""
    payload = event.payload
    run_id = payload.get("run_id", "unknown")
    workflow_id = payload.get("workflow_id") or payload.get("graph_id", "unknown")
    target_app = payload.get("target_app", workflow_id)

    try:
        invoker(
            "evals_persist_score",
            run_id=run_id,
            workflow_type=payload.get("workflow_type", "freshness-trigger"),
            target_app=target_app,
            vuln_class=payload.get("vuln_class", ""),
            domain_class=payload.get("domain_class", ""),
            source="freshness",
            scoring={
                "f1": 0,
                "precision": 0,
                "recall": 0,
                "pass_rate": 0,
                "avg_score": 0,
                "staleness_triggered": True,
            },
        )
        logger.info(
            "freshness: persisted staleness eval for run=%s target=%s",
            run_id, target_app,
        )
    except Exception as exc:
        # Defensive: never break the caller
        logger.warning("freshness: persist failed for run=%s: %s", run_id, exc)


def handle_freshness_check(event: Event, invoker: Any) -> dict[str, Any]:
    """Check eval freshness for the experiment and trigger if stale.

    Returns a summary dict for dispatch logging.  Exceptions are caught
    internally — the caller's path is NEVER broken.
    """
    try:
        payload = event.payload
        run_id = payload.get("run_id", "")
        workflow_id = payload.get("workflow_id") or payload.get("graph_id", "")
        target_app = payload.get("target_app", workflow_id)

        threshold_s = _get_staleness_threshold()
        try:
            last_eval_ts = _get_last_eval_timestamp(invoker, run_id, target_app)
        except Exception as exc:
            # Loud, typed, and no persist: an unknown state is not "stale".
            logger.error("freshness: lookup failed for target=%s: %s", target_app, exc)
            return {"action": "error", "target_app": target_app, "error": str(exc)}

        if _is_stale(last_eval_ts, threshold_s):
            _persist_freshness_eval(invoker, event)
            return {
                "action": "triggered",
                "target_app": target_app,
                "last_eval_ts": last_eval_ts,
                "threshold_s": threshold_s,
            }
        else:
            logger.debug(
                "freshness: target=%s is fresh (last_eval=%s, threshold=%s)",
                target_app, last_eval_ts, threshold_s,
            )
            return {
                "action": "skipped_fresh",
                "target_app": target_app,
                "last_eval_ts": last_eval_ts,
                "threshold_s": threshold_s,
            }
    except Exception as exc:
        # Defensive top-level guard
        logger.warning("freshness handler error: %s", exc)
        return {"action": "error", "error": str(exc)}
