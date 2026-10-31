"""Regression coverage for the durable Evals run convergence path."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from factory.evals.runtime.adapters import doc_store_reader
from factory.evals.runtime.adapters.backfill_runs import backfill
from factory.evals.runtime.run_record_contract import (
    EVALUATION_RUN_RECORD_KIND,
    build_record,
)


def _record(
    run_id: str, timestamp: str = "2026-07-01T00:00:00+00:00",
    pass_rate: float = 1.0,
) -> tuple[str, dict]:
    passed = pass_rate == 1.0
    payload = {
        "experiment_name": "convergence", "verdict": "PASS" if passed else "FAIL",
        "source": "experiment", "pass_rate": pass_rate, "avg_score": pass_rate,
        "total_cases": 1, "passed_cases": int(passed),
        "failed_cases": int(not passed), "duration_ms": 0.0,
        "evaluators_used": ["output"],
        "case_results": [{"passed": passed, "score": pass_rate}],
        "case_scores": [pass_rate], "agent": {}, "summary": {},
    }
    return build_record(
        run_id=run_id, record_kind=EVALUATION_RUN_RECORD_KIND,
        terminal_state="completed", timestamp=timestamp, payload=payload,
    )


def _wrapper(artifact: tuple[str, dict]) -> dict:
    doc_id, record = artifact
    return {"id": doc_id, "data": record}


def test_reader_accepts_only_versioned_terminal_artifacts() -> None:
    projection = build_record(
        run_id="score", record_kind="evaluation_score_projection",
        terminal_state="scored", payload={"experiment_name": "convergence"},
    )
    docs = {
        "documents": [
            _wrapper(_record("valid")),
            {"id": "legacy", "data": {"run_id": "legacy", "f1": 0.7}},
            _wrapper(projection),
        ],
    }
    with patch(
        "factory.evals.runtime.adapters.doc_store_reader._get_invoker",
        return_value=lambda *_args, **_kwargs: docs,
    ):
        runs = doc_store_reader.list_runs()
    assert [run["run_id"] for run in runs] == ["valid"]


def test_backfill_routes_through_canonical_writer_and_counts_created(tmp_path) -> None:
    path = tmp_path / "eval_runs"
    path.mkdir()
    (path / "run.json").write_text(json.dumps({
        "run_id": "bf", "experiment_name": "backfill",
        "summary": {"total_cases": 1, "passed": 1},
    }))
    calls: list[dict] = []
    import factory.evals.runtime.adapters.backfill_runs as module
    with patch.object(module, "_RUNS_DIR", path):
        result = backfill(
            lambda _tool, **kwargs: calls.append(kwargs) or {
                "schema_version": "v1", "ok": True, "data": {"status": "created"},
                "error": None, "idempotency_key": None,
            },
        )
    assert result["migrated"] == 1
    assert calls[0]["run_id"] == "bf"
    assert "storage_doc_insert" not in str(calls)


def test_backfill_counts_existing_and_conflicting_immutable_records(tmp_path) -> None:
    path = tmp_path / "eval_runs"
    path.mkdir()
    for name in ("existing", "conflict"):
        (path / f"{name}.json").write_text(json.dumps({
            "run_id": name, "experiment_name": name,
        }))
    statuses = iter(("matched", "conflict"))
    import factory.evals.runtime.adapters.backfill_runs as module
    with patch.object(module, "_RUNS_DIR", path):
        result = backfill(lambda *_args, **_kwargs: {
            "schema_version": "v1", "ok": True, "data": {"status": next(statuses)},
            "error": None, "idempotency_key": None,
        })
    assert result["already_present"] == 1
    assert result["conflicts"] == 1


def test_reader_keeps_dashboard_trend_shape() -> None:
    docs = {"documents": [
        _wrapper(_record("old", pass_rate=0.5)),
        _wrapper(_record("new", "2026-07-02T00:00:00+00:00", 1.0)),
    ]}
    with patch(
        "factory.evals.runtime.adapters.doc_store_reader._get_invoker",
        return_value=lambda *_args, **_kwargs: docs,
    ):
        run = doc_store_reader.list_runs()[0]
    assert run["trend_direction"] == "up"
    assert {"run_id", "pass_rate_delta", "regression_state"} <= run.keys()
