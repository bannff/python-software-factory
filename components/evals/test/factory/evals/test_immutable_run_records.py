"""Canonical immutable Evals record tests."""
from __future__ import annotations

import asyncio
from unittest.mock import patch

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from factory.evals.mcp.run_record_tools import register
from factory.evals.runtime.run_record_contract import build_record


def _kwargs(**extra):
    return {
        "run_id": "run-1", "experiment_name": "exp", "verdict": "PASS",
        "pass_rate": 1.0, "avg_score": 1.0, "total_cases": 1, "passed": 1,
        "case_results": [{"passed": True, "score": 1.0}],
        "case_scores": [1.0], **extra,
    }


def _tool(invoker):
    mcp = ToolCatalog("records")
    register(mcp)
    tool = asyncio.run(mcp.get_tool("evals_record_run"))
    return lambda **kwargs: tool.fn(**kwargs).model_dump(mode="json")["data"]


def _conditional_store():
    documents: dict[str, dict] = {}

    def invoker(tool: str, **kwargs):
        if tool == "storage_doc_get":
            document = documents.get(kwargs["doc_id"])
            return {"data": document, "id": kwargs["doc_id"]} if document else {}
        assert tool == "storage_doc_create_or_match"
        document = documents.get(kwargs["doc_id"])
        if document is None:
            documents[kwargs["doc_id"]] = kwargs["data"]
            return {"status": "created"}
        existing_hash = document["content_hash"]
        return {
            "status": "matched" if existing_hash == kwargs["content_hash"] else "conflict",
            "existing_content_hash": existing_hash,
        }

    return documents, invoker


def test_hash_authenticates_timestamp_and_orders_nested_keys() -> None:
    first = build_record(
        run_id="r", record_kind="evaluation_run", terminal_state="completed",
        timestamp="stable", payload={"summary": {"b": 2, "a": 1}},
    )
    reordered = build_record(
        run_id="r", record_kind="evaluation_run", terminal_state="completed",
        timestamp="stable", payload={"summary": {"a": 1, "b": 2}},
    )
    changed_receipt = build_record(
        run_id="r", record_kind="evaluation_run", terminal_state="completed",
        timestamp="changed", payload={"summary": {"a": 1, "b": 2}},
    )
    assert first[0] == reordered[0] == changed_receipt[0] == "eval-v2-r"
    assert first[1]["content_hash"] == reordered[1]["content_hash"]
    assert first[1]["content_hash"] != changed_receipt[1]["content_hash"]


def test_default_timestamp_is_utc_rfc3339_and_changes_per_new_record() -> None:
    first = build_record(
        run_id="r", record_kind="evaluation_run", terminal_state="completed",
        payload={"summary": {"stable": True}},
    )
    second = build_record(
        run_id="r", record_kind="evaluation_run", terminal_state="completed",
        payload={"summary": {"stable": True}},
    )
    assert first[1]["timestamp"].endswith("Z")
    assert "T" in first[1]["timestamp"]
    assert first[1]["timestamp"] != second[1]["timestamp"] or first[1]["content_hash"] == second[1]["content_hash"]


def test_canonical_retry_reuses_derived_timestamp() -> None:
    documents, invoker = _conditional_store()
    with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
        record = _tool(invoker)
        first = record(**_kwargs())
        retry = record(**_kwargs(timestamp=""))
    assert first["status"] == "created"
    assert retry["status"] == "matched"
    assert retry["timestamp"] == first["timestamp"]


def test_legacy_blank_timestamp_is_not_rewritten() -> None:
    documents, invoker = _conditional_store()
    legacy = build_record(
        run_id="legacy", record_kind="evaluation_run", terminal_state="completed",
        timestamp="", payload={"experiment_name": "exp"},
    )[1]
    legacy["timestamp"] = ""
    legacy["content_hash"] = __import__("factory.evals.runtime.run_record_contract", fromlist=["semantic_content_hash"]).semantic_content_hash(legacy)
    documents["eval-v2-legacy"] = legacy
    with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
        result = _tool(invoker)(**_kwargs(run_id="legacy"))
    assert result["status"] == "conflict"
    assert documents["eval-v2-legacy"]["timestamp"] == ""



def test_legacy_blank_timestamp_read_status_is_completed() -> None:
    from factory.evals.runtime.adapters import doc_store_reader
    from factory.evals.runtime.run_record_contract import semantic_content_hash

    _, record = build_record(
        run_id="legacy-read", record_kind="evaluation_run", terminal_state="completed",
        timestamp="stable", payload={
            "experiment_name": "exp", "verdict": "PASS", "pass_rate": 1.0,
            "avg_score": 1.0, "total_cases": 1, "passed_cases": 1,
            "failed_cases": 0,
        },
    )
    record["timestamp"] = ""
    record["content_hash"] = semantic_content_hash(record)

    def invoker(tool: str, **kwargs):
        assert tool == "storage_doc_find"
        return {"documents": [{"id": "eval-v2-legacy-read", "data": record}]}

    with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
        runs = doc_store_reader.list_runs()
    assert runs[0]["completion_status"] == "completed_time_unavailable"
def test_v2_identity_is_isolated_from_v1_documents() -> None:
    doc_id, record = build_record(
        run_id="r", record_kind="evaluation_run", terminal_state="completed",
        payload={"summary": {"stable": True}},
    )
    assert doc_id == "eval-v2-r"
    assert doc_id != "eval-r"
    assert record["schema_version"] == 2


def test_payload_cannot_overwrite_the_canonical_envelope() -> None:
    doc_id, record = build_record(
        run_id="canonical", record_kind="evaluation_run", terminal_state="completed",
        timestamp="receipt", payload={
            "schema_version": 99, "record_kind": "injected", "terminal_state": "open",
            "run_id": "injected", "payload_value": "preserved",
        },
    )

    assert doc_id == "eval-v2-canonical"
    assert record["schema_version"] == 2
    assert record["record_kind"] == "evaluation_run"
    assert record["terminal_state"] == "completed"
    assert record["run_id"] == "canonical"
    assert record["payload_value"] == "preserved"


def test_canonical_writer_matches_equal_retries_and_preserves_conflicts() -> None:
    documents, invoker = _conditional_store()
    with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
        record = _tool(invoker)
        created = record(**_kwargs())
        matched = record(**_kwargs())
        conflict = record(**_kwargs(
            verdict="FAIL", pass_rate=0.0, avg_score=0.0, passed=0,
            case_results=[{"passed": False, "score": 0.0}], case_scores=[0.0],
        ))

    assert [created["status"], matched["status"], conflict["status"]] == [
        "created", "matched", "conflict",
    ]
    assert [created["persisted"], matched["persisted"], conflict["persisted"]] == [
        True, True, False,
    ]
    assert documents["eval-v2-run-1"]["pass_rate"] == 1.0
    assert conflict["existing_content_hash"] == created["content_hash"]


def test_score_projection_has_an_isolated_document_identity() -> None:
    documents, invoker = _conditional_store()
    with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
        record = _tool(invoker)
        artifact = record(**_kwargs())
        score = record(**_kwargs(
            record_kind="evaluation_score_projection", terminal_state="scored",
            verdict="SCORED", score_projection={"f1": 1.0},
        ))

    assert artifact["doc_id"] == "eval-v2-run-1"
    assert score["doc_id"] == "eval-score-v2-run-1"
    assert set(documents) == {"eval-v2-run-1", "eval-score-v2-run-1"}
    assert documents["eval-v2-run-1"]["record_kind"] == "evaluation_run"
    assert documents["eval-score-v2-run-1"]["record_kind"] == "evaluation_score_projection"


def test_canonical_writer_returns_stable_pointer_only_after_commit() -> None:
    _, invoker = _conditional_store()
    with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
        record = _tool(invoker)
        created = record(**_kwargs())
        matched = record(**_kwargs())
        conflict = record(**_kwargs(
            verdict="FAIL", pass_rate=0.0, avg_score=0.0, passed=0,
            case_results=[{"passed": False, "score": 0.0}], case_scores=[0.0],
        ))

    assert created["pointer"] == matched["pointer"] == {
        "collection": "eval_results", "doc_id": "eval-v2-run-1",
        "record_kind": "evaluation_run", "schema_version": 2,
        "revision": "v2", "content_hash": created["content_hash"],
    }
    assert created["projection_key"] == matched["projection_key"]
    assert "pointer" not in conflict
    assert "projection_key" not in conflict
