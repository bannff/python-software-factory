"""bd:python-factory-0ttck — auto-eval bridge refinements (follow-up to z85kh).

Two observability/config refinements, no core-behavior change:
  1. Surface caller-vs-rows summary divergence at WARNING (never fail the write).
  2. Make the fallback pass threshold configurable via env, default 1.0.
"""
from __future__ import annotations

import importlib
import logging
from typing import Any

import factory.events.runtime._dispatch_evals as de
from factory.events.runtime._dispatch_evals import (
    _bridge_auto_eval_to_evals,
    _normalize_case,
    _resolve_pass_threshold,
)


def _capturing_invoker(captured: dict[str, Any]):
    def invoker(tool_name: str, **kwargs: Any) -> dict[str, Any]:
        if tool_name == "evals_record_run":
            captured.update(kwargs)
            return {"persisted": True, "status": "created"}
        return {}
    return invoker


# --- CHANGE 1: summary divergence surfacing -------------------------------

def test_diverging_caller_summary_warns_but_still_persists_rows_derived(caplog) -> None:
    """Caller pass_rate 0.9 vs rows-derived 0.333 → WARNING, but write still uses rows."""
    captured: dict[str, Any] = {}
    result = {
        "summary": {"pass_rate": 0.9, "avg_score": 0.9},
        "results": [
            {"evaluator": "a", "score": 1.0},   # passes
            {"evaluator": "b", "score": 0.0},   # fails
            {"evaluator": "c", "score": 0.0},   # fails
        ],
    }
    with caplog.at_level(logging.WARNING, logger=de.logger.name):
        out = _bridge_auto_eval_to_evals(
            _capturing_invoker(captured), "run-diverge", "g-1", result["summary"], result,
        )

    # Still persists, rows-derived values authoritative (1/3 pass).
    assert out.get("persisted") is True
    assert captured["pass_rate"] == round(1 / 3, 3)
    assert captured["passed"] == 1 and captured["failed_cases"] == 2
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("divergence" in m and "run-diverge" in m and "pass_rate" in m for m in warnings)
    assert any("avg_score" in m for m in warnings)


def test_matching_caller_summary_logs_nothing(caplog) -> None:
    """Caller summary that matches rows-derived aggregates emits no divergence warning."""
    captured: dict[str, Any] = {}
    result = {
        "summary": {"pass_rate": round(1 / 3, 6), "avg_score": round(1 / 3, 6)},
        "results": [
            {"evaluator": "a", "score": 1.0},
            {"evaluator": "b", "score": 0.0},
            {"evaluator": "c", "score": 0.0},
        ],
    }
    with caplog.at_level(logging.WARNING, logger=de.logger.name):
        out = _bridge_auto_eval_to_evals(
            _capturing_invoker(captured), "run-match", "g-2", result["summary"], result,
        )

    assert out.get("persisted") is True
    assert not [r for r in caplog.records if "divergence" in r.getMessage()]


def test_missing_or_nonnumeric_caller_summary_does_not_warn(caplog) -> None:
    """Absent/non-numeric caller aggregates are skipped, not warned on."""
    captured: dict[str, Any] = {}
    result = {
        "summary": {"pass_rate": "n/a"},   # non-numeric → skipped
        "results": [{"evaluator": "a", "score": 1.0}],
    }
    with caplog.at_level(logging.WARNING, logger=de.logger.name):
        _bridge_auto_eval_to_evals(
            _capturing_invoker(captured), "run-nan", "g-3", result["summary"], result,
        )
    assert not [r for r in caplog.records if "divergence" in r.getMessage()]


# --- CHANGE 2: configurable pass threshold --------------------------------

def test_default_threshold_keeps_099_below_1_failing() -> None:
    """Default (no env) → threshold 1.0, so a 0.9 row is not passed."""
    _, score, passed = _normalize_case({"score": 0.9})
    assert score == 0.9 and passed is False


def test_env_threshold_lets_09_pass(monkeypatch) -> None:
    """COMPANION_X_EVAL_PASS_THRESHOLD=0.8 → a 0.9 row normalizes to passed=True."""
    monkeypatch.setattr(de, "_PASS_THRESHOLD", 0.8)
    _, score, passed = _normalize_case({"score": 0.9})
    assert score == 0.9 and passed is True
    # Explicit boolean still wins over the heuristic.
    _, _, forced = _normalize_case({"score": 0.9, "passed": False})
    assert forced is False


def test_resolve_threshold_default_when_env_absent(monkeypatch) -> None:
    monkeypatch.delenv("COMPANION_X_EVAL_PASS_THRESHOLD", raising=False)
    assert _resolve_pass_threshold() == 1.0


def test_resolve_threshold_reads_valid_env(monkeypatch) -> None:
    monkeypatch.setenv("COMPANION_X_EVAL_PASS_THRESHOLD", "0.8")
    assert _resolve_pass_threshold() == 0.8


def test_resolve_threshold_falls_back_on_bad_values(monkeypatch) -> None:
    """Non-float, zero, and negative all fall back to 1.0."""
    for bad in ("abc", "0", "0.0", "-0.5", "nan", "inf"):
        monkeypatch.setenv("COMPANION_X_EVAL_PASS_THRESHOLD", bad)
        assert _resolve_pass_threshold() == 1.0, bad


def test_module_import_default_threshold_is_one() -> None:
    """Fresh import with no env → module constant is byte-identical 1.0."""
    reloaded = importlib.reload(de)
    try:
        assert reloaded._PASS_THRESHOLD == 1.0
    finally:
        importlib.reload(de)
