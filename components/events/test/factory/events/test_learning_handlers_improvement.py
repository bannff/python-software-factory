"""Tests for the workflow improvement learning handler (bd-kq6u).

Verdict transitions, dedup, error path, current-run exclusion, Hypothesis
property linking verdict to threshold, plus a YAML loader smoke test for
``auto-improvement-on-reward-computed``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import given, settings, strategies as st

from factory.events.runtime.learning_contracts import (
    VERDICT_BASELINE_SET, VERDICT_IMPROVED,
    VERDICT_REGRESSED, VERDICT_STABLE,
)
from factory.events.runtime.learning_handlers.improvement import (
    _DEFAULT_WINDOW, _IMPROVEMENT_THRESHOLD, _MIN_RUNS_FOR_SIGNAL,
    handle_workflow_improvement,
)
from factory.events.runtime.models import Event
from factory.events.runtime.subscriptions import SubscriptionDefinition

_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

def _doc(run_id: str, f1: float, when: datetime) -> dict[str, Any]:
    return {"id": f"eval-{run_id}", "data": {
        "run_id": run_id, "workflow_type": "dast",
        "target_app": "WebGoat", "vuln_class": "IDOR",
        "f1": f1, "created_at": when.isoformat(),
    }}

def _priors(scores: list[float]) -> list[dict[str, Any]]:
    return [_doc(f"run-{i}", f, _T0 - timedelta(days=i + 1))
            for i, f in enumerate(scores)]

def _make_invoker(docs: list[dict[str, Any]] | None = None, *,
                  already_published: bool = False, raise_on_find: bool = False):
    docs = docs or []
    published: list[tuple[str, dict[str, Any]]] = []

    def invoker(tool_name: str, **kwargs: Any) -> Any:
        if tool_name == "events_query_events":
            if (kwargs.get("event_type") == "workflow.improvement"
                    and already_published):
                return {"events": [{"id": "evt-prior"}], "total": 1}
            return {"events": [], "total": 0}
        if tool_name == "storage_doc_find":
            if raise_on_find:
                raise RuntimeError("storage backend down")
            assert kwargs["collection"] == "eval_results"
            assert kwargs["limit"] == _DEFAULT_WINDOW + 1
            return {"documents": docs}
        if tool_name == "events_publish":
            published.append((kwargs["event_type"], kwargs["payload"]))
            return {"event_id": "evt-improvement"}
        raise AssertionError(f"unexpected tool: {tool_name}")

    return invoker, published

def _event(score: float = 0.5, run_id: str = "run-current") -> Event:
    return Event(
        source="events.rewards", type="reward.computed",
        payload={
            "run_id": run_id, "workflow_run_id": f"wf-{run_id}",
            "workflow_type": "dast", "target_app": "WebGoat",
            "vuln_class": "IDOR", "score": score, "profile_version": "v1",
        },
    )

def test_baseline_set_when_too_few_priors() -> None:
    invoker, published = _make_invoker(_priors([0.4, 0.5]))
    result = handle_workflow_improvement(_event(score=0.9), invoker)
    assert result["verdict"] == VERDICT_BASELINE_SET
    assert result["baseline_score"] == 0.0
    assert result["delta"] == 0.0
    assert result["baseline_window_n"] == _DEFAULT_WINDOW
    # Audit trail: prior run ids still persisted (bounded by window) even
    # when count < signal threshold.
    assert sorted(result["baseline_run_ids"]) == ["run-0", "run-1"]
    assert published[0][0] == "workflow.improvement"
    assert published[0][1]["verdict"] == VERDICT_BASELINE_SET

def test_baseline_set_when_zero_priors() -> None:
    invoker, _ = _make_invoker([])
    result = handle_workflow_improvement(_event(score=0.9), invoker)
    assert result["verdict"] == VERDICT_BASELINE_SET
    assert result["baseline_run_ids"] == []

@pytest.mark.parametrize(
    "priors,current,expected_verdict,expected_delta",
    [
        ([0.50, 0.50, 0.50, 0.50], 0.70, VERDICT_IMPROVED, 0.20),
        ([0.80, 0.80, 0.80, 0.80], 0.50, VERDICT_REGRESSED, -0.30),
        ([0.70, 0.70, 0.70, 0.70], 0.72, VERDICT_STABLE, 0.02),
    ],
)
def test_verdict_at_threshold_boundaries(
    priors, current, expected_verdict, expected_delta,
) -> None:
    invoker, published = _make_invoker(_priors(priors))
    result = handle_workflow_improvement(_event(score=current), invoker)
    assert result["verdict"] == expected_verdict
    assert round(result["delta"], 4) == round(expected_delta, 4)
    assert published[0][1]["verdict"] == expected_verdict
    assert "run-current" not in result["baseline_run_ids"]

def test_dedup_via_already_published_short_circuits() -> None:
    invoker, published = _make_invoker([], already_published=True)
    result = handle_workflow_improvement(_event(), invoker)
    assert result["deduped"] is True
    assert result["idempotency_key"].startswith("improvement:wf-run-current:")
    assert published == []

def test_storage_error_path_returns_skipped_without_raising() -> None:
    invoker, published = _make_invoker([], raise_on_find=True)
    result = handle_workflow_improvement(_event(), invoker)
    assert result.get("skipped") is True
    assert "storage backend down" in result.get("error", "")
    assert published == []

def test_baseline_run_ids_excludes_current_run() -> None:
    """Even if current run is somehow surfaced, it is filtered out."""
    docs = [
        _doc("run-current", 0.99, _T0),
        _doc("run-1", 0.40, _T0 - timedelta(days=1)),
        _doc("run-2", 0.60, _T0 - timedelta(days=2)),
        _doc("run-3", 0.50, _T0 - timedelta(days=3)),
    ]
    invoker, _ = _make_invoker(docs)
    result = handle_workflow_improvement(
        _event(score=0.90, run_id="run-current"), invoker)
    assert "run-current" not in result["baseline_run_ids"]
    assert sorted(result["baseline_run_ids"]) == ["run-1", "run-2", "run-3"]

def test_baseline_window_caps_at_n() -> None:
    """We ask for N+1 docs; baseline_run_ids must never exceed N."""
    invoker, _ = _make_invoker(_priors([0.5] * (_DEFAULT_WINDOW + 1)))
    result = handle_workflow_improvement(_event(score=0.55), invoker)
    assert len(result["baseline_run_ids"]) == _DEFAULT_WINDOW

@settings(max_examples=50, deadline=None)
@given(
    priors=st.lists(
        st.floats(0.0, 1.0, allow_nan=False, allow_infinity=False),
        min_size=0, max_size=12),
    current=st.floats(0.0, 1.0, allow_nan=False, allow_infinity=False),
)
def test_verdict_matches_threshold_logic(priors, current) -> None:
    invoker, _ = _make_invoker(_priors(priors))
    result = handle_workflow_improvement(_event(score=current), invoker)

    if len(priors) < _MIN_RUNS_FOR_SIGNAL:
        assert result["verdict"] == VERDICT_BASELINE_SET
        assert result["baseline_score"] == 0.0
        assert result["delta"] == 0.0
        return

    window = priors[:_DEFAULT_WINDOW]
    expected_baseline = round(sum(window) / len(window), 4)
    expected_delta = round(current - (sum(window) / len(window)), 4)
    assert result["baseline_score"] == expected_baseline
    assert result["delta"] == expected_delta
    if expected_delta >= _IMPROVEMENT_THRESHOLD:
        assert result["verdict"] == VERDICT_IMPROVED
    elif expected_delta <= -_IMPROVEMENT_THRESHOLD:
        assert result["verdict"] == VERDICT_REGRESSED
    else:
        assert result["verdict"] == VERDICT_STABLE

def test_auto_improvement_subscription_yaml_loads_with_priority_seven() -> None:
    """Built-in YAML pins event_type, handler, priority — keeps fanout order."""
    subs_dir = (Path(__file__).resolve().parents[3]
                / "src/factory/events/subscriptions")
    yaml_path = subs_dir / "auto-improvement-on-reward-computed.yaml"
    assert yaml_path.exists(), "subscription YAML missing"
    sub = SubscriptionDefinition.model_validate(
        yaml.safe_load(yaml_path.read_text()))
    assert sub.id == "auto-improvement-on-reward-computed"
    assert sub.event_type == "reward.computed"
    assert sub.handler == "mcp:workflow_improvement_dispatch"
    assert sub.priority == 7
    assert sub.enabled is True
