"""Convergence-check learning handler."""

from __future__ import annotations

import logging
from typing import Any

from ..learning_contracts import validate_learning_payload
from ..mcp_result import successful_data
from ..models import Event
from ._common import _already_published, _base_payload, _publish, _is_gt_reward

logger = logging.getLogger(__name__)


def handle_convergence_check(event: Event, invoker: Any) -> dict[str, Any]:
    """Record reward metrics and emit convergence state."""
    payload = event.payload
    # Only ground-truth F1 rewards feed pipeline-f1 baselines/drift — quality
    # (llm-judge), feedback and penalty signals are excluded (bd:pfvo9 Q5).
    if not _is_gt_reward(payload):
        return {"skipped": True, "reason": "non-GT reward (excluded from pipeline-f1)"}
    convergence_key = _convergence_key(payload)
    if _already_published(invoker, "convergence.checked", convergence_key):
        return {
            **_base_payload(event),
            "status": "checked",
            "metric_id": "pipeline-f1",
            "converged": False,
            "baseline_window": "7d",
            "comparison_window": "24h",
            "metrics_recorded": 0,
            "regression_signal": None,
            "baseline_tag": None,
            "deduped": True,
        }

    labels = {
        "workflow": payload.get("workflow_id") or payload.get("graph_id", ""),
        "app": payload.get("target_app", ""),
        # bd:python-factory-7ut47 — bucket convergence metrics by
        # domain_class with vuln_class fallback so wine + workout runs
        # don't pollute the security pipeline-f1 baselines.
        "vuln_class": (
            payload.get("domain_class") or payload.get("vuln_class", "")
        ),
        "run_id": payload.get("run_id", ""),
    }
    metrics_to_record = [
        ("pipeline-f1", payload.get("score", 0)),
        ("pipeline-precision", payload.get("precision", 0)),
        ("pipeline-recall", payload.get("recall", 0)),
        ("pipeline-true-positives", payload.get("true_positives", 0)),
        ("pipeline-false-positives", payload.get("false_positives", 0)),
        ("pipeline-false-negatives", payload.get("false_negatives", 0)),
        ("pipeline-tokens-minted", payload.get("reward_value", 0)),
    ]

    recorded = 0
    for metric_id, value in metrics_to_record:
        try:
            result = invoker(
                "metrics_record", metric_id=metric_id, value=value, labels=labels
            )
            if successful_data(result) is None:
                raise RuntimeError("metrics record failed")
            recorded += 1
        except Exception as exc:
            logger.warning("learning metrics record failed for %s: %s", metric_id, exc)

    try:
        result = invoker(
            "metrics_detect_drift",
            metric_id="pipeline-f1",
            baseline_period="7d",
            current_period="24h",
            threshold=0.1,
        )
        drift = successful_data(result)
        if drift is None:
            raise RuntimeError("metrics drift failed")
    except Exception as exc:
        # On error we cannot determine convergence — treat as not converged.
        logger.warning("learning metrics drift failed (%s)", type(exc).__name__)
        drift = {"drifted": True, "reason": "error"}

    derived_payload = {
        **_base_payload(event),
        "status": "checked",
        "metric_id": "pipeline-f1",
        "converged": _is_converged(drift),
        "baseline_window": "7d",
        "comparison_window": "24h",
        "metrics_recorded": recorded,
        "regression_signal": drift.get("regression_signal"),
        "baseline_tag": drift.get("baseline_tag"),
    }
    derived_payload = validate_learning_payload("convergence.checked", derived_payload)
    _publish(invoker, event, "convergence.checked", derived_payload)
    return {**derived_payload, "drift_details": drift}


def _is_converged(drift: dict[str, Any]) -> bool:
    """Convergence = baseline and current agree (no drift) and we had data.

    The metrics adapter contract returns ``{"drifted": bool, ...}`` plus
    ``"reason": "insufficient_data"`` when either window is empty. A naive
    ``not drifted`` flip would falsely report convergence in that case, so
    we guard explicitly.
    """
    if drift.get("reason") in ("insufficient_data", "error"):
        return False
    return not bool(drift.get("drifted", True))


def _convergence_key(payload: dict[str, Any]) -> str:
    """Stable dedupe key for convergence emission."""
    return (
        f"convergence:{payload.get('workflow_run_id') or payload.get('run_id')}:"
        f"{payload.get('profile_version', 'v1')}"
    )
