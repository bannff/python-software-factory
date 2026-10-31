"""bd:python-factory-z85kh — auto-eval bridge honors the full evaluation_run contract.

The old bridge fabricated a phantom 1-case record (`max(1, len(rows))`) with no
`case_scores`, tripping several `validate_evaluation_run` checks (count parity,
list-length parity, per-case `passed`/`score`, positional score match). These
tests pin the corrected behavior: abstain on empty rows, and otherwise emit a
payload that passes `validate_evaluation_run`.
"""
from __future__ import annotations

from typing import Any

from factory.events.runtime._dispatch_evals import _bridge_auto_eval_to_evals
from factory.evals.runtime.run_record_validation import validate_evaluation_run


def _capturing_invoker(captured: dict[str, Any]):
    def invoker(tool_name: str, **kwargs: Any) -> dict[str, Any]:
        if tool_name == "evals_record_run":
            captured.update(kwargs)
            return {"persisted": True, "status": "created"}
        return {}
    return invoker


def _payload_from(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Reassemble the payload exactly as ``evals_record_run`` builds it."""
    passed = kwargs["passed"]
    total = kwargs["total_cases"]
    failed = kwargs.get("failed_cases")
    resolved_failed = total - passed if failed is None else failed
    return {
        "experiment_name": kwargs["experiment_name"], "verdict": kwargs["verdict"],
        "source": kwargs["source"], "pass_rate": kwargs["pass_rate"],
        "avg_score": kwargs["avg_score"], "total_cases": total,
        "passed_cases": passed, "failed_cases": resolved_failed,
        "duration_ms": 0.0, "evaluators_used": kwargs.get("evaluators_used", []),
        "case_results": kwargs["case_results"], "case_scores": kwargs["case_scores"],
        "agent": kwargs.get("agent", {}), "summary": kwargs.get("summary", {}),
    }


def test_zero_results_abstains_without_recording() -> None:
    """No rows → abstain: no evals_record_run, explicit reason, no phantom record."""
    calls: list[str] = []

    def invoker(tool_name: str, **kwargs: Any) -> dict[str, Any]:
        calls.append(tool_name)
        return {}

    out = _bridge_auto_eval_to_evals(
        invoker, "run-empty", "g-1", {"pass_rate": 0.0}, {"results": []},
    )
    assert "evals_record_run" not in calls
    assert out == {"persisted": False, "reason": "no case results to record"}


def test_mixed_rows_produce_valid_persisted_payload() -> None:
    """N rows (some passing, some failing) → payload passes validation and persists."""
    captured: dict[str, Any] = {}
    result = {
        "summary": {"pass_rate": 0.9, "avg_score": 0.9},
        "results": [
            {"evaluator": "a", "score": 1.0},   # passes (>= 1.0)
            {"evaluator": "b", "score": 0.5},   # fails
            {"evaluator": "c", "score": 0.0},   # fails
        ],
    }

    out = _bridge_auto_eval_to_evals(
        _capturing_invoker(captured), "run-mixed", "g-9", result["summary"], result,
    )

    assert out.get("persisted") is True
    assert captured["total_cases"] == 3
    assert captured["passed"] + captured["failed_cases"] == captured["total_cases"]
    assert len(captured["case_scores"]) == captured["total_cases"]
    assert captured["passed"] == 1 and captured["failed_cases"] == 2
    assert validate_evaluation_run(_payload_from(captured)) is None


def test_rows_missing_passed_and_score_are_normalized() -> None:
    """Rows lacking `passed`/`score` are normalized, not rejected."""
    captured: dict[str, Any] = {}
    result = {
        "summary": {},
        "results": [
            {"evaluator": "x"},              # no score → 0.0, passed False
            {"score": 1.0},                  # no evaluator → "", passed True
            {"evaluator": "z", "score": 5.0},  # out-of-range → clamped to 1.0, passed True
        ],
    }

    out = _bridge_auto_eval_to_evals(
        _capturing_invoker(captured), "run-missing", "g-3", {}, result,
    )

    assert out.get("persisted") is True
    assert captured["total_cases"] == 3
    assert captured["passed"] == 2 and captured["failed_cases"] == 1
    assert captured["case_scores"] == [0.0, 1.0, 1.0]
    assert all(isinstance(c["passed"], bool) for c in captured["case_results"])
    assert validate_evaluation_run(_payload_from(captured)) is None
