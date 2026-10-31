"""Tests for evals dashboard summary sort behavior (bd:python-factory-yxu1).

Verifies the experiments list is sorted newest-first within each group,
and that the recent-trend chart uses the most recent runs.
"""
from __future__ import annotations

from typing import Any

from factory.evals.mcp.views import _build_dashboard_summary


def _run_record(
    *,
    experiment_name: str,
    timestamp: str,
    pass_rate: float = 1.0,
    verdict: str = "PASS",
    regression_state: str = "baseline",
    run_id: str = "",
) -> dict[str, Any]:
    """Build a minimal run dict shaped like list_runs() output."""
    return {
        "run_id": run_id or f"{experiment_name}-{timestamp}",
        "experiment_name": experiment_name,
        "timestamp": timestamp,
        "verdict": verdict,
        "pass_rate": pass_rate,
        "avg_score": pass_rate,
        "total_cases": 1,
        "passed_cases": 1 if verdict == "PASS" else 0,
        "failed_cases": 0 if verdict == "PASS" else 1,
        "duration_ms": 0.0,
        "evaluators_used": [],
        "case_scores": [pass_rate],
        "agent": {"model_id": "m"},
        "previous_run_id": None,
        "pass_rate_delta": 0.0,
        "avg_score_delta": 0.0,
        "trend_direction": "flat",
        "regression_state": regression_state,
    }


def test_experiments_sorted_newest_first_within_same_group() -> None:
    """Within identical group keys, newest run sorts to position [0]."""
    # All PASS, all baseline, all ad_hoc → identical group bucket.
    runs = [
        _run_record(experiment_name="exp-c-newest", timestamp="2025-01-03T00:00:00Z"),
        _run_record(experiment_name="exp-b-middle", timestamp="2025-01-02T00:00:00Z"),
        _run_record(experiment_name="exp-a-oldest", timestamp="2025-01-01T00:00:00Z"),
    ]
    summary = _build_dashboard_summary(runs, [])
    names = [item["experiment_name"] for item in summary["experiments"]]
    assert names == ["exp-c-newest", "exp-b-middle", "exp-a-oldest"]
    assert summary["experiments"][0]["latest_timestamp"] == "2025-01-03T00:00:00Z"
    assert summary["experiments"][-1]["latest_timestamp"] == "2025-01-01T00:00:00Z"


def test_group_precedence_beats_timestamp() -> None:
    """A regressed older experiment still ranks above a clean newer PASS."""
    runs = [
        _run_record(  # newest, clean PASS → later group
            experiment_name="exp-clean-newest",
            timestamp="2025-01-10T00:00:00Z",
            verdict="PASS",
            regression_state="baseline",
        ),
        _run_record(  # older, regressed → first group
            experiment_name="exp-regressed-old",
            timestamp="2025-01-01T00:00:00Z",
            verdict="FAIL",
            regression_state="regressed",
        ),
    ]
    summary = _build_dashboard_summary(runs, [])
    assert summary["experiments"][0]["experiment_name"] == "exp-regressed-old"
    assert summary["experiments"][0]["regression_state"] == "regressed"
    assert summary["experiments"][1]["experiment_name"] == "exp-clean-newest"


def test_recent_trend_chart_uses_most_recent_runs() -> None:
    """series should reflect the 10 most recent runs in chronological order."""
    # list_runs() returns newest-first; build 15 runs in that shape.
    runs = [
        _run_record(
            experiment_name=f"run-{idx:02d}",
            timestamp=f"2025-01-{idx:02d}T00:00:00Z",
        )
        for idx in range(15, 0, -1)  # newest first
    ]
    summary = _build_dashboard_summary(runs, [])
    assert len(summary["series"]) == 10
    # series is reversed(runs[:10]) → chronological left-to-right:
    # oldest-of-recent first, newest last. The 10 most recent are 15..6;
    # reversed gives 6..15.
    labels = [point["label"] for point in summary["series"]]
    assert labels[0] == "run-06"
    assert labels[-1] == "run-15"
    assert "run-01" not in labels
    assert "run-05" not in labels
