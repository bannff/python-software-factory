"""Telemetry reward handler — failures become learning signal (bd:hv5rv).

Subscribes to ``metrics.record`` (published one hop after ``graph.completed``
by the auto-metrics flow, carrying ``tool_error_rate``). Routes the run's
error rate through the learning seam's ``telemetry`` source → a signed
NEGATIVE reward (``PENALIZED``, zero tokens) so process failures shape
behavior via recall, not just dashboards.

Isolation is structural: this rides ``metrics.record`` while the gt-findings
task reward rides ``graph.completed`` → they never share a ``compute()`` call,
so a positive task signal cannot suppress the penalty (meta-architect
86f91240). The idempotency key is source-scoped (``:telemetry``) so it does
not collide with the gt-findings reward on the same run. Telemetry's
``source_id`` is auto-excluded from the GT pipeline-f1 pools by
``_is_gt_reward``. Reuses ``_emit_reward_event`` (DRY).
"""
from __future__ import annotations

import logging
from typing import Any

from .models import Event
from .rewards_handler import _emit_reward_event
from .learning_result import normalize_learning_result

logger = logging.getLogger(__name__)

__all__ = ["handle_telemetry_reward"]


def handle_telemetry_reward(event: Event, invoker: Any) -> dict[str, Any]:
    """Penalize a run for its tool_error_rate; abstain on a clean run."""
    payload = event.payload
    run_id = payload.get("run_id", "")
    rate = payload.get("tool_error_rate")
    if not run_id or rate is None:
        return {"skipped": True, "reason": "no run_id/tool_error_rate"}
    domain_class = payload.get("domain_class", "") or ""
    try:
        result = normalize_learning_result(invoker(
            "learning_compute_reward",
            run_id=run_id,
            domain_class=domain_class,
            workflow_type="telemetry",
            tool_error_rate=rate,
        ))
    except Exception as exc:
        logger.warning("telemetry reward: compute failed (%s)", type(exc).__name__)
        return {"skipped": True, "error": "reward_computation_failed"}
    if result is None:
        return {"skipped": True, "error": "reward_computation_failed"}
    if not result.get("source_id"):
        return {"skipped": True, "reason": "clean run (no penalty)"}
    # Canonical top-level fields drive emission; nested raw is evidence only.
    if domain_class:
        payload["domain_class"] = domain_class
    reward = _emit_reward_event(invoker, event, result, key_suffix="telemetry")
    logger.info(
        "telemetry reward: run=%s error_rate=%s verdict=%s",
        run_id, rate, reward.get("verdict"),
    )
    return {"run_id": run_id, "reward": reward}
