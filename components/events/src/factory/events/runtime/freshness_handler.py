"""Eval-freshness staleness handler (bd:python-factory-v7imt.4).

Shared handler for two convergence triggers:
1. ON-COMPLETION: graph.completed / swarm.completed events
2. CADENCE: eval.freshness.due events from AgentRunner timer

Logic: check the target experiment's last-eval timestamp vs a
configurable staleness threshold.  If stale, persist a freshness
eval via the evals brick's evals_persist_score MCP tool (through
invoker — no cross-brick imports).

Defensive: a persist failure is logged but NEVER breaks the caller's
completion or timer path.
"""

from __future__ import annotations

import logging
import os
import time
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


def _get_last_eval_timestamp(invoker: Any, run_id: str, target_app: str) -> float | None:
    """Query the evals brick for the latest eval timestamp for this target.

    Returns epoch seconds or None if no prior eval exists.
    """
    try:
        result = invoker("evals_get_latest_score", target_app=target_app or run_id)
        data = successful_data(result)
        if data is not None:
            ts = data.get("timestamp") or data.get("scored_at")
            if ts is not None:
                return float(ts)
        return None
    except Exception as exc:
        logger.debug("freshness: could not fetch last eval for %s: %s", target_app, exc)
        return None


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
        last_eval_ts = _get_last_eval_timestamp(invoker, run_id, target_app)

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
