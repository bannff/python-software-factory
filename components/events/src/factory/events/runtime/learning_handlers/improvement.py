"""Workflow improvement learning handler — bd python-factory-kq6u.

Subscribes to ``reward.computed`` (priority 7). Reads the last N=10 prior
runs of the same ``(workflow_type, target_app, vuln_class)`` tuple from the
storage ``eval_results`` collection, computes ``baseline_score`` (mean F1
over the older runs), compares the current run, and emits
``workflow.improvement`` with one of:

* ``baseline_set``  — fewer than ``_MIN_RUNS_FOR_SIGNAL`` priors → no signal
* ``improved``      — ``delta >= +threshold``
* ``regressed``     — ``delta <= -threshold``
* ``stable``        — ``|delta| < threshold``

The threshold is module-local for now (``_IMPROVEMENT_THRESHOLD = 0.05``).
Per the meta-architect verdict (mem ``e85fdbbb``), the eventual home is
per-workflow ``success_rubric.improvement_threshold`` — that arrives with
bd-tirq's WorkflowSpec evolution. Until then we keep one constant; the
override pathway is an explicit override-by-future-rubric, not env vars.
"""

from __future__ import annotations

import logging
from typing import Any

from factory.mcp_utils.interface import ToolResult

from ..learning_contracts import (
    VERDICT_BASELINE_SET,
    VERDICT_IMPROVED,
    VERDICT_REGRESSED,
    VERDICT_STABLE,
    validate_learning_payload,
)
from ..models import Event
from ._common import _already_published, _base_payload, _publish, _is_gt_reward

logger = logging.getLogger(__name__)

_DEFAULT_WINDOW = 10
_MIN_RUNS_FOR_SIGNAL = 3
_IMPROVEMENT_THRESHOLD = 0.05
_COLLECTION = "eval_results"


def handle_workflow_improvement(event: Event, invoker: Any) -> dict[str, Any]:
    """Compute improvement vs rolling baseline; emit ``workflow.improvement``."""
    payload = event.payload
    # Only ground-truth F1 rewards have a comparable rolling baseline; quality
    # / feedback / penalty signals are excluded from the F1 pool (bd:pfvo9 Q5).
    if not _is_gt_reward(payload):
        return {"skipped": True, "reason": "non-GT reward (excluded from F1 baseline)"}
    current_score = float(payload.get("score", 0) or 0)
    target_app = payload.get("target_app", "")
    vuln_class = payload.get("vuln_class", "")
    # bd:python-factory-7ut47 — baseline lookups + idempotency keys MUST
    # bucket by domain_class with vuln_class fallback so domain agents
    # (wine, workout, ...) compute their own rolling baseline instead of
    # mixing in security runs.
    domain_class = payload.get("domain_class") or vuln_class
    workflow_type = payload.get("workflow_type", "auto")
    workflow_run_id = payload.get("workflow_run_id") or payload.get("run_id", "")
    profile_version = payload.get("profile_version", "v1")
    current_run_id = payload.get("run_id", "")

    idempotency_key = (
        f"improvement:{workflow_run_id}:{profile_version}:n{_DEFAULT_WINDOW}"
    )
    if _already_published(invoker, "workflow.improvement", idempotency_key):
        return {
            **_base_payload(event),
            "status": "checked",
            "current_score": current_score,
            "baseline_score": 0.0,
            "delta": 0.0,
            "verdict": VERDICT_BASELINE_SET,
            "baseline_window_n": _DEFAULT_WINDOW,
            "baseline_run_ids": [],
            "idempotency_key": idempotency_key,
            "deduped": True,
        }

    # Read prior eval_results scoped to this workflow's signature. The query
    # is keyed on ``vuln_class`` to match how ``_persist_score`` writes today
    # (security default). When the persister gains a ``domain_class`` column
    # in the same diff, callers that set domain_class get scoped baselines;
    # security callers continue to bucket on vuln_class.
    query: dict[str, Any] = {
        "workflow_type": workflow_type,
        "target_app": target_app,
        "vuln_class": vuln_class,
    }
    if domain_class and domain_class != vuln_class:
        # Domain agent — bucket by the canonical domain field.
        query = {
            "workflow_type": workflow_type,
            "target_app": target_app,
            "domain_class": domain_class,
        }
    try:
        result = invoker(
            "storage_doc_find",
            collection=_COLLECTION,
            query=query,
            limit=_DEFAULT_WINDOW + 1,
        )
    except Exception as exc:  # pragma: no cover - non-blocking observability
        logger.warning("workflow.improvement: storage_doc_find failed: %s", exc)
        return {"skipped": True, "error": str(exc)}

    docs = _extract_docs(result)
    baseline_docs = _select_baseline(docs, current_run_id)

    if len(baseline_docs) < _MIN_RUNS_FOR_SIGNAL:
        verdict = VERDICT_BASELINE_SET
        baseline_score = 0.0
        delta = 0.0
    else:
        baseline_score = sum(float(d["f1"]) for d in baseline_docs) / len(baseline_docs)
        delta = current_score - baseline_score
        if delta >= _IMPROVEMENT_THRESHOLD:
            verdict = VERDICT_IMPROVED
        elif delta <= -_IMPROVEMENT_THRESHOLD:
            verdict = VERDICT_REGRESSED
        else:
            verdict = VERDICT_STABLE

    derived_payload = {
        **_base_payload(event),
        "status": "checked",
        "current_score": current_score,
        "baseline_score": round(baseline_score, 4),
        "delta": round(delta, 4),
        "verdict": verdict,
        "baseline_window_n": _DEFAULT_WINDOW,
        "baseline_run_ids": [d["run_id"] for d in baseline_docs],
        "idempotency_key": idempotency_key,
    }
    derived_payload = validate_learning_payload("workflow.improvement", derived_payload)
    _publish(invoker, event, "workflow.improvement", derived_payload)
    return derived_payload


def _extract_docs(result: Any) -> list[dict[str, Any]]:
    """Pull the inner ``data`` dicts out of a doc_find response.

    storage.mcp.operational.doc_find returns
    ``{"documents": [{"id": ..., "data": {...}}, ...]}`` — each ``data`` is
    the original record stored by ``_persist_score``. Shape-tolerant: also
    accepts the older ``{"docs": [...]}`` envelope from earlier adapters.
    """
    if isinstance(result, ToolResult):
        if not result.ok or result.data is None:
            return []
        raw = getattr(result.data, "documents", [])
        return [entry.data for entry in raw if isinstance(entry.data, dict)]
    if not isinstance(result, dict) or result.get("ok") is False:
        return []
    payload = result.get("data") if result.get("ok") is True else result
    if not isinstance(payload, dict):
        return []
    raw = payload.get("documents") or payload.get("docs") or []
    out: list[dict[str, Any]] = []
    for entry in raw:
        if isinstance(entry, dict) and isinstance(entry.get("data"), dict):
            out.append(entry["data"])
        elif isinstance(entry, dict):
            out.append(entry)
    return out


def _select_baseline(
    docs: list[dict[str, Any]], current_run_id: str,
) -> list[dict[str, Any]]:
    """Filter/sort prior eval rows into the baseline window."""
    scored = [
        d
        for d in docs
        if d.get("f1") is not None
        and d.get("created_at")
        and d.get("run_id")
        and d.get("run_id") != current_run_id
    ]
    scored.sort(key=lambda d: str(d.get("created_at", "")), reverse=True)
    return scored[:_DEFAULT_WINDOW]
