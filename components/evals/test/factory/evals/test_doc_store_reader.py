"""Tests for fail-closed schema-v2 Evals document readers."""
from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch

from factory.evals.runtime.adapters.doc_store_reader import get_run, list_runs
from factory.evals.runtime.run_record_contract import (
    EVALUATION_RUN_RECORD_KIND,
    build_record,
    semantic_content_hash,
)
from factory.mcp_utils.interface import ToolResult
from factory.storage.mcp.contracts.operational import DocumentData, DocFindOutput, DocGetOutput


def _run(run_id: str = "run-1", **extra) -> tuple[str, dict]:
    timestamp = extra.pop("timestamp", "2026-07-01T00:00:00+00:00")
    payload = {
        "experiment_name": "test-exp", "verdict": "PASS", "source": "experiment",
        "pass_rate": 1.0, "avg_score": 0.8, "total_cases": 1,
        "passed_cases": 1, "failed_cases": 0, "duration_ms": 0.0,
        "evaluators_used": ["output"],
        "case_results": [{"passed": True, "score": 0.8}],
        "case_scores": [0.8], "agent": {}, "summary": {},
    }
    payload.update(extra)
    return build_record(
        run_id=run_id, record_kind=EVALUATION_RUN_RECORD_KIND,
        terminal_state="completed", timestamp=timestamp,
        payload=payload,
    )


def _wrapper(artifact: tuple[str, dict], wrapper_id: str | None = None) -> dict:
    doc_id, record = artifact
    return {"id": wrapper_id or doc_id, "data": record}


def test_list_and_get_accept_only_canonical_v2_runs() -> None:
    artifact = _run()
    wrapper = _wrapper(artifact)

    def invoker(tool_name: str, **_kwargs):
        return {"documents": [wrapper]} if tool_name == "storage_doc_find" else wrapper

    with patch(
        "factory.evals.runtime.adapters.doc_store_reader._get_invoker",
        return_value=invoker,
    ):
        assert [run["run_id"] for run in list_runs()] == ["run-1"]
        assert get_run("run-1")["run_id"] == "run-1"


def test_reader_rejects_v1_projection_id_mismatch_and_tamper() -> None:
    v1_id, v1 = _run("v1")
    v1["schema_version"] = 1
    v1["content_hash"] = semantic_content_hash(v1)
    projection = build_record(
        run_id="projection", record_kind="evaluation_score_projection",
        terminal_state="scored", payload={"experiment_name": "test-exp"},
    )
    mismatch = _wrapper(_run("mismatch"), wrapper_id="eval-v2-other")
    tampered_id, tampered = _run("tampered")
    tampered = deepcopy(tampered)
    tampered["pass_rate"] = 0.0

    docs = {
        "documents": [
            {"id": v1_id, "data": v1}, _wrapper(projection), mismatch,
            {"id": tampered_id, "data": tampered},
        ],
    }
    with patch(
        "factory.evals.runtime.adapters.doc_store_reader._get_invoker",
        return_value=lambda *_args, **_kwargs: docs,
    ):
        assert list_runs() == []


def test_list_runs_excludes_projections_and_enriches_full_artifacts() -> None:
    old = _wrapper(_run("old", pass_rate=0.8))
    new = _wrapper(_run(
        "new", pass_rate=1.0, avg_score=1.0,
        timestamp="2026-07-02T00:00:00+00:00",
    ))
    projection = _wrapper(build_record(
        run_id="score", record_kind="evaluation_score_projection",
        terminal_state="scored", payload={"experiment_name": "test-exp"},
    ))
    docs = {"documents": [old, new, projection]}
    with patch(
        "factory.evals.runtime.adapters.doc_store_reader._get_invoker",
        return_value=lambda *_args, **_kwargs: docs,
    ):
        runs = list_runs()
    assert [run["run_id"] for run in runs] == ["new", "old"]
    assert runs[0]["trend_direction"] == "up"


def test_readers_accept_real_storage_dto_tool_results() -> None:
    artifact = _run("typed")
    doc_id, record = artifact

    def invoker(tool_name: str, **_kwargs):
        if tool_name == "storage_doc_find":
            return ToolResult(data=DocFindOutput(documents=[DocumentData(id=doc_id, data=record)]))
        return ToolResult(data=DocGetOutput(found=True, collection="eval_results", id=doc_id, data=record))

    with patch("factory.evals.runtime.adapters.doc_store_reader._get_invoker", return_value=invoker):
        assert [run["run_id"] for run in list_runs()] == ["typed"]
        assert get_run("typed")["run_id"] == "typed"

    with patch("factory.evals.runtime.adapters.doc_store_reader._get_invoker", return_value=lambda *_args, **_kwargs: ToolResult(ok=False, error="down")):
        assert list_runs() == []
        assert get_run("typed") is None
