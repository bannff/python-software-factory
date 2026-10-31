"""Fake-only tests for durable simulation run artifacts."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from factory.evals.mcp import run_record_tools
from factory.evals.runtime.ports import ExperimentReport
from factory.evals.runtime.run_artifacts import build_run_artifacts
from factory.evals.runtime.run_record_contract import build_run_request


def _report() -> ExperimentReport:
    def evidence(correlation_id: str) -> dict:
        return {
            "correlation_id": correlation_id,
            "target_session": {"session": correlation_id},
            "target_span_snapshot": [{"name": "target"}],
            "actor_turns": [{"turn": 1, "target_message": correlation_id}],
        }

    return ExperimentReport(
        experiment_name="duplicate-names",
        evaluator_names=["helpfulness", "goal_success"],
        case_results=[
            {"case_name": "duplicate", "evaluator": "helpfulness", "score": 1.0,
             "passed": True, "reason": "ok", "simulation_evidence": evidence("first")},
            {"case_name": "duplicate", "evaluator": "helpfulness", "score": 0.5,
             "passed": False, "reason": "no", "simulation_evidence": evidence("second")},
            {"case_name": "duplicate", "evaluator": "goal_success", "score": 1.0,
             "passed": True, "reason": "ok", "simulation_evidence": evidence("first")},
            {"case_name": "duplicate", "evaluator": "goal_success", "score": 0.5,
             "passed": False, "reason": "no", "simulation_evidence": evidence("second")},
        ],
        summary={
            "aggregate_strategy": "sdk_run_evaluations_flatten",
            "overall_score": 0.75, "pass_rate": 0.5, "total_cases": 4,
            "native_reports": [{"cases": [{"name": "duplicate"}]}],
        },
    )


def _request(run_id: str) -> dict:
    return build_run_request(
        _report(), run_id, {"kind": "normalized_session"},
        "evaluation", 12.0, artifacts=build_run_artifacts(_report()),
    )


def _record(payload: dict, invoker):
    mcp = ToolCatalog("record-run")
    run_record_tools.register(mcp)
    tool = asyncio.run(mcp.get_tool("evals_record_run"))
    with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
        result = tool.fn(**payload).model_dump(mode="json")
    assert result["ok"] is True
    return result["data"]


def test_artifacts_use_ordinal_keys_and_separate_target_actor_evidence():
    artifacts = build_run_artifacts(_report())

    assert artifacts["schema_version"] == 1
    assert artifacts["aggregate"]["name"] == "sdk_run_evaluations_flatten"
    assert [item["evaluator_key"] for item in artifacts["evaluator_matrix"]] == [
        "evaluator-0", "evaluator-1",
    ]
    manifests = artifacts["case_manifests"]
    assert [item["case_key"] for item in manifests] == ["case-0", "case-1"]
    assert [item["metadata"]["name"] for item in manifests] == ["duplicate", "duplicate"]
    assert all(len(item["result_keys"]) == 2 for item in manifests)
    assert [item["case_key"] for item in artifacts["target_sessions"]] == ["case-0", "case-1"]
    assert [item["case_key"] for item in artifacts["actor_evidence"]] == ["case-0", "case-1"]
    refs = {result["result_key"] for evaluator in artifacts["evaluator_matrix"] for result in evaluator["results"]}
    assert refs == {key for manifest in manifests for key in manifest["result_keys"]}


def test_record_run_rejects_non_json_artifacts_without_storage_write():
    writes: list[dict] = []

    def invoker(tool_name: str, **kwargs: object) -> dict:
        writes.append({"tool_name": tool_name, **kwargs})
        return {}

    payload = {
        "run_id": "strict-json", "experiment_name": "strict", "verdict": "FAIL",
        "pass_rate": 0.0, "avg_score": 0.0, "total_cases": 1, "passed": 0,
        "case_results": [{"passed": False, "score": 0.0}],
        "case_scores": [0.0], "artifacts": {
            "target_sessions": [{"target_session": SimpleNamespace()}],
            "actor_evidence": [{"exporter": lambda: None}],
        },
    }
    result = _record(payload, invoker)

    assert result["persisted"] is False
    assert result["run_id"] == "strict-json"
    assert "invalid durable JSON" in result["reason"]
    assert writes == []


def test_record_run_preserves_artifact_payload_on_an_equal_retry():
    documents: dict[str, dict] = {}

    def invoker(tool_name: str, **kwargs: object) -> dict:
        assert tool_name == "storage_doc_create_or_match"
        doc_id = str(kwargs["doc_id"])
        existing = documents.get(doc_id)
        if existing is None:
            documents[doc_id] = kwargs["data"]
            return {"status": "created"}
        if existing["content_hash"] == kwargs["content_hash"]:
            return {"status": "matched"}
        return {"status": "conflict", "existing_content_hash": existing["content_hash"]}

    old = {
        "run_id": "old", "experiment_name": "old", "verdict": "PASS",
        "pass_rate": 1.0, "avg_score": 1.0, "total_cases": 1, "passed": 1,
        "case_results": [{"passed": True, "score": 1.0}],
        "case_scores": [1.0],
    }
    assert _record(old, invoker)["persisted"] is True
    request = _request("retry")
    assert _record(request, invoker)["status"] == "created"
    assert _record(request, invoker)["status"] == "matched"

    assert "artifacts" not in documents["eval-v2-old"]
    assert documents["eval-v2-retry"]["artifacts"]["schema_version"] == 1


def test_artifacts_keep_duplicate_evaluator_display_names_distinct():
    report = _report()
    for ordinal, row in enumerate(report.case_results):
        row["evaluator"] = "judge"
        row["evaluator_ordinal"] = ordinal // 2
    report.summary["native_reports"] = [{"id": "first"}, {"id": "second"}]

    artifacts = build_run_artifacts(report)

    assert [item["evaluator_key"] for item in artifacts["evaluator_matrix"]] == [
        "evaluator-0", "evaluator-1",
    ]
    assert [item["metadata"]["name"] for item in artifacts["evaluator_matrix"]] == ["judge", "judge"]
    assert [item["evaluator_keys"] for item in artifacts["native_reports"]] == [
        ["evaluator-0"], ["evaluator-1"],
    ]


def test_record_run_rejects_protected_inline_content_before_storage_write():
    writes: list[dict] = []

    def invoker(tool_name: str, **kwargs: object) -> dict:
        writes.append({"tool_name": tool_name, **kwargs})
        return {"status": "created"}

    payload = {
        "run_id": "protected-inline", "experiment_name": "protected",
        "verdict": "FAIL", "pass_rate": 0.0, "avg_score": 0.0,
        "total_cases": 1, "passed": 0,
        "summary": {"body": "evals-private-canary@example.test"},
        "artifacts": {"artifact_ref": "pc_v1_abcdefghijklmnopqrstuv"},
    }
    result = _record(payload, invoker)

    assert result["persisted"] is False
    assert result["reason"] == "protected inline content is forbidden"
    assert writes == []
