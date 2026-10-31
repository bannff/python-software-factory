"""Regression tests for canonical Evals aggregate fields."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest

from factory.evals.runtime.run_record_contract import (
    EVALUATION_RUN_RECORD_KIND,
    build_record,
    document_id,
    semantic_content_hash,
)


@pytest.fixture()
def tmp_runs_dir(tmp_path: Path):
    """Provide a fake document-store reader through tool_invoker."""
    documents: dict[str, dict] = {}

    def invoker(tool_name: str, **kwargs):
        collection = kwargs["collection"]
        if tool_name == "storage_doc_insert":
            key = f"{collection}:{kwargs['doc_id']}"
            documents[key] = {"id": kwargs["doc_id"], "data": kwargs["data"]}
            return {"id": kwargs["doc_id"]}
        if tool_name == "storage_doc_find":
            rows = [
                row for name, row in documents.items()
                if name.startswith(f"{collection}:")
            ]
            return {"documents": rows[:kwargs.get("limit", 100)]}
        if tool_name == "storage_doc_get":
            key = f"{collection}:{kwargs['doc_id']}"
            return documents.get(key, {"error": "not_found"})
        return {}

    with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
        yield invoker


def _artifact(data: dict) -> tuple[str, dict]:
    """Build the canonical immutable envelope and its derived document ID."""
    return build_record(
        run_id=data["run_id"], record_kind=EVALUATION_RUN_RECORD_KIND,
        terminal_state="completed", timestamp=data.get("timestamp", ""),
        payload={
            key: value for key, value in data.items()
            if key not in {"run_id", "timestamp"}
        },
    )


def _store(invoker, data: dict) -> None:
    doc_id, record = _artifact(data)
    invoker(
        "storage_doc_insert", collection="eval_results", doc_id=doc_id, data=record,
    )


def _data(run_id: str, **extra) -> dict:
    return {
        "run_id": run_id, "experiment_name": "glm5-dast-webgoat",
        "timestamp": "2026-04-12T23:14:24.072755+00:00", "verdict": "PASS",
        "source": "experiment", "pass_rate": 1.0, "avg_score": 0.883,
        "total_cases": 3, "passed_cases": 3, "failed_cases": 0,
        "evaluators_used": ["output"],
        "case_results": [
            {"case_name": "case-1", "score": 0.85, "passed": True},
            {"case_name": "case-2", "score": 0.9, "passed": True},
            {"case_name": "case-3", "score": 0.9, "passed": True},
        ],
        "case_scores": [0.85, 0.9, 0.9], "agent": {"model_id": "zai.glm-5"},
        "summary": {}, **extra,
    }


class TestNullAggregatesRegression:
    """Readers return normalized aggregates from accepted artifact records."""

    def test_get_run_returns_complete_canonical_aggregates(self, tmp_runs_dir):
        from factory.evals.runtime.adapters.doc_store_reader import get_run

        _store(tmp_runs_dir, _data("607c333d2c76"))
        result = get_run("607c333d2c76")

        assert result is not None
        assert (result["passed_cases"], result["total_cases"], result["failed_cases"]) == (3, 3, 0)
        assert (result["pass_rate"], result["avg_score"]) == (1.0, 0.883)

    def test_get_run_preserves_explicit_aggregates(self, tmp_runs_dir):
        from factory.evals.runtime.adapters.doc_store_reader import get_run

        _store(tmp_runs_dir, _data(
            "bbbb33334444", pass_rate=0.5, avg_score=0.42, total_cases=99,
            passed_cases=50, failed_cases=49,
            case_results=[{"case_name": "x", "score": 1.0, "passed": True}],
        ))
        result = get_run("bbbb33334444")

        assert result is not None
        assert (result["pass_rate"], result["avg_score"]) == (0.5, 0.42)
        assert (result["total_cases"], result["passed_cases"], result["failed_cases"]) == (99, 50, 49)

    def test_dashboard_summary_consistent_with_get_run(self, tmp_runs_dir):
        from factory.evals.runtime.adapters.doc_store_reader import get_run, list_runs

        _store(tmp_runs_dir, _data("607c333d2c76"))
        detail = get_run("607c333d2c76")
        summary = list_runs()[0]

        assert detail is not None
        for field in ("pass_rate", "avg_score", "total_cases", "passed_cases", "failed_cases"):
            assert detail[field] == summary[field]

    def test_reader_rejects_v1_projection_id_mismatch_and_tamper(self, tmp_runs_dir):
        from factory.evals.runtime.adapters.doc_store_reader import get_run, list_runs

        v1_id, v1 = _artifact(_data("legacy"))
        v1["schema_version"] = 1
        v1["content_hash"] = semantic_content_hash(v1)
        projection_id, projection = build_record(
            run_id="projection", record_kind="evaluation_score_projection",
            terminal_state="scored", payload=_data("projection"),
        )
        mismatch_id, mismatch = _artifact(_data("mismatch"))
        tampered_id, tampered = _artifact(_data("tampered"))
        tampered = deepcopy(tampered)
        tampered["pass_rate"] = 0.0
        missing_id, missing = _artifact(_data("missing"))
        missing.pop("total_cases")
        missing["content_hash"] = semantic_content_hash(missing)
        malformed_id, malformed = _artifact(_data("malformed"))
        malformed["content_hash"] = "not-a-semantic-hash"

        for doc_id, record in (
            (v1_id, v1), (projection_id, projection),
            (document_id("other", EVALUATION_RUN_RECORD_KIND), mismatch),
            (tampered_id, tampered), (missing_id, missing),
            (malformed_id, malformed),
        ):
            tmp_runs_dir(
                "storage_doc_insert", collection="eval_results",
                doc_id=doc_id, data=record,
            )

        assert list_runs() == []
        assert get_run("legacy") is None
        assert get_run("tampered") is None
        assert mismatch_id == document_id("mismatch", EVALUATION_RUN_RECORD_KIND)


class TestDeriveAggregatesHelper:
    """Unit tests for the pure derive_aggregates function."""

    def test_empty_cases(self):
        from factory.evals.runtime.adapters._aggregates import derive_aggregates

        assert derive_aggregates([]) == {
            "total_cases": 0, "passed": 0, "failed": 0,
            "pass_rate": 0.0, "avg_score": 0.0,
        }

    def test_all_passed(self):
        from factory.evals.runtime.adapters._aggregates import derive_aggregates

        result = derive_aggregates([
            {"passed": True, "score": 0.85}, {"passed": True, "score": 0.9},
            {"passed": True, "score": 0.9},
        ])
        assert (result["total_cases"], result["passed"], result["failed"]) == (3, 3, 0)
        assert result["pass_rate"] == 1.0
        assert abs(result["avg_score"] - 0.883) < 0.001

    def test_mixed_pass_fail(self):
        from factory.evals.runtime.adapters._aggregates import derive_aggregates

        result = derive_aggregates([
            {"passed": True, "score": 1.0}, {"passed": False, "score": 0.2},
        ])
        assert (result["total_cases"], result["passed"], result["failed"]) == (2, 1, 1)
        assert (result["pass_rate"], result["avg_score"]) == (0.5, 0.6)

    def test_none_scores_treated_as_zero(self):
        from factory.evals.runtime.adapters._aggregates import derive_aggregates

        result = derive_aggregates([{"passed": True, "score": None}])
        assert (result["avg_score"], result["pass_rate"]) == (0.0, 1.0)
