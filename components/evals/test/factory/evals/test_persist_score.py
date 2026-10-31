"""Tests for the legacy GT score projection facade."""
from __future__ import annotations

from factory.evals.runtime._persist_score import persist_score_result

_SCORING = {
    "precision": 0.8, "recall": 0.84, "f1": 0.82, "true_positives": 4,
    "false_positives_count": 1, "false_negatives": 2,
    "matched": [{"finding": {}}, {"finding": {}}], "missed": [{"gt_id": "g1"}],
}


def test_score_uses_canonical_writer_with_an_isolated_projection() -> None:
    captured: dict = {}

    def invoker(tool: str, **kwargs):
        assert tool == "evals_record_run"
        captured.update(kwargs)
        return {"schema_version": "v1", "ok": True, "data": {"persisted": True, "status": "created", "doc_id": "eval-score-run-x"}, "error": None, "idempotency_key": None}

    assert persist_score_result(invoker, "run-x", "sast", "DVWA", "SQLi", _SCORING)
    assert captured["record_kind"] == "evaluation_score_projection"
    assert captured["terminal_state"] == "scored"
    assert captured["timestamp"].endswith("Z")
    assert captured["score_projection"]["f1"] == 0.82
    assert captured["score_projection"]["matched_count"] == 2


def test_score_retry_preserves_the_same_run_identity() -> None:
    calls: list[dict] = []

    def invoker(_tool: str, **kwargs):
        calls.append(kwargs)
        return {"schema_version": "v1", "ok": True, "data": {"persisted": True, "status": "matched"}, "error": None, "idempotency_key": None}

    assert persist_score_result(invoker, "run-42", "dast", "App", "X", _SCORING)
    assert persist_score_result(invoker, "run-42", "dast", "App", "X", _SCORING)
    assert [call["run_id"] for call in calls] == ["run-42", "run-42"]
    assert all(call["record_kind"] == "evaluation_score_projection" for call in calls)


def test_score_failure_is_best_effort_and_empty_id_short_circuits() -> None:
    assert not persist_score_result(lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError()),
                                    "run-z", "dast", "App", "X", _SCORING)
    assert not persist_score_result(lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError()),
                                    "", "dast", "App", "X", _SCORING)
