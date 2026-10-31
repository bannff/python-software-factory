"""Regression coverage for vacuous legacy run persistence."""
from __future__ import annotations

from pathlib import Path

from factory.evals.runtime.adapters import run_results_store


def test_zero_case_run_is_fail_closed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_results_store, "_RUNS_DIR", tmp_path / "eval_runs")
    run_id = run_results_store.save_run(
        experiment_name="empty",
        case_results=[],
        summary={},
        evaluators_used=["output"],
        model_id="model",
        system_prompt="prompt",
    )
    record = run_results_store.get_run(run_id)
    assert record is not None
    assert record["verdict"] == "FAIL"
    assert record["summary"] == {
        "pass_rate": 0.0, "avg_score": 0.0, "total_cases": 0,
        "passed": 0, "failed": 0, "duration_ms": 0.0,
    }
