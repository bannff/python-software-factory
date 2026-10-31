"""Exact immutable Evals pointer verification tests."""
from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from hypothesis import given, strategies as st

from factory.evals.interface import create_server, verify_record_pointer
from factory.evals.mcp import record_verification_tools, run_record_tools
from factory.evals.runtime.run_record_contract import semantic_content_hash
from factory.mcp_utils.interface import ToolResult
from factory.storage.mcp.contracts.immutable import DocCreateOrMatchOutput
from factory.storage.mcp.contracts.operational import DocGetOutput


def _tools(invoker):
    mcp = ToolCatalog("record-verification")
    run_record_tools.register(mcp)
    record_verification_tools.register(mcp)

    def call(name: str, **kwargs):
        tool = asyncio.run(mcp.get_tool(name))
        with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
            return tool.fn(**kwargs).model_dump(mode="json")["data"]

    return call


def _store():
    documents: dict[str, dict] = {}

    def invoker(name: str, **kwargs):
        key = kwargs["doc_id"]
        if name == "storage_doc_create_or_match":
            if key not in documents:
                documents[key] = deepcopy(kwargs["data"])
                return {"status": "created"}
            return {"status": "matched"}
        if name == "storage_doc_get":
            if key not in documents:
                return {"error": "not_found", "collection": kwargs["collection"], "id": key}
            return {
                "collection": kwargs["collection"], "id": key,
                "data": deepcopy(documents[key]),
            }
        raise AssertionError(name)

    return documents, invoker


def _record(call, **extra):
    request = {
        "run_id": "run-verify", "experiment_name": "exp", "verdict": "PASS",
        "pass_rate": 1.0, "avg_score": 1.0, "total_cases": 1, "passed": 1,
        "case_results": [{"passed": True, "score": 1.0}],
        "case_scores": [1.0], "summary": {"stable": True},
        "artifacts": {"schema_version": 1, "model_inputs": ["sealed://dataset"]},
        "score_projection": {"artifact_refs": ["sealed://model-input"]},
        **extra,
    }
    return call("evals_record_run", **request)


def _verify(call, pointer):
    return call("evals_verify_record_pointer", **pointer)


def test_match_returns_exact_deterministic_consumer_envelope() -> None:
    _, invoker = _store()
    call = _tools(invoker)
    pointer = _record(call)["pointer"]

    result = _verify(call, pointer)

    assert result == {
        "verified": True, "pointer": pointer, "run_id": "run-verify",
        "summary": {"stable": True},
        "case_results": [{"passed": True, "score": 1.0}],
        "case_scores": [1.0], "verdict": "PASS", "pass_rate": 1.0,
        "avg_score": 1.0, "total_cases": 1, "passed_cases": 1,
        "failed_cases": 0, "evaluators_used": [],
        "artifact_refs": ["sealed://model-input"],
        "artifacts": {"schema_version": 1, "model_inputs": ["sealed://dataset"]},
    }


def test_equal_pointer_is_byte_equivalent_across_fresh_mcp_runtimes() -> None:
    _, invoker = _store()
    pointer = _record(_tools(invoker))["pointer"]
    first = _verify(_tools(invoker), pointer)
    second = _verify(_tools(invoker), pointer)

    encode = lambda value: json.dumps(value, separators=(",", ":"), sort_keys=True)
    assert encode(first) == encode(second)


@given(st.text(min_size=1, max_size=40).filter(lambda value: value != "original"))
def test_any_semantic_summary_tamper_is_rejected(value: str) -> None:
    documents, invoker = _store()
    call = _tools(invoker)
    pointer = _record(call, summary={"value": "original"})["pointer"]
    documents[pointer["doc_id"]]["summary"]["value"] = value

    assert _verify(call, pointer)["reason"] == "tampered_record"


def test_every_persisted_field_is_authenticated() -> None:
    documents, invoker = _store()
    call = _tools(invoker)
    pointer = _record(call)["pointer"]
    original = deepcopy(documents[pointer["doc_id"]])

    for field in original:
        changed = deepcopy(original)
        changed[field] = {"tampered": True}
        documents[pointer["doc_id"]] = changed
        assert _verify(call, pointer)["verified"] is False, field

        missing = deepcopy(original)
        del missing[field]
        documents[pointer["doc_id"]] = missing
        assert _verify(call, pointer)["verified"] is False, field


def test_malformed_missing_and_uncomputed_reads_fail_closed() -> None:
    _, invoker = _store()
    call = _tools(invoker)
    pointer = _record(call)["pointer"]
    malformed = {**pointer, "content_hash": "sha256:nope"}
    missing = {**pointer, "doc_id": "eval-missing"}

    assert _verify(call, malformed)["reason"] == "malformed_content_hash"
    assert _verify(call, missing)["reason"] == "missing_record"

    def uncomputed(name: str, **kwargs):
        return {"computed": False} if name == "storage_doc_get" else invoker(name, **kwargs)

    assert _verify(_tools(uncomputed), pointer)["reason"] == "uncomputed_storage_response"


def test_stale_divergent_record_and_malformed_stored_hash_fail_closed() -> None:
    documents, invoker = _store()
    call = _tools(invoker)
    pointer = _record(call)["pointer"]
    document = documents[pointer["doc_id"]]
    document["summary"] = {"stable": False}
    document["content_hash"] = semantic_content_hash(document)

    assert _verify(call, pointer)["reason"] == "content_hash_mismatch"
    document["content_hash"] = "sha256:invalid"
    assert _verify(call, pointer)["reason"] == "malformed_stored_content_hash"


@given(st.sampled_from([
    ("collection", "other"), ("record_kind", "unknown"),
    ("revision", "v1"), ("doc_id", "eval-other"),
    ("content_hash", "sha256:" + "0" * 64),
]))
def test_changed_pointer_field_is_rejected(mutation: tuple[str, object]) -> None:
    _, invoker = _store()
    call = _tools(invoker)
    pointer = _record(call)["pointer"]
    changed = {**pointer, mutation[0]: mutation[1]}

    assert _verify(call, changed)["verified"] is False


def test_interface_fastmcp_and_brick_metadata_register_verifier() -> None:
    assert callable(verify_record_pointer)
    mcp = create_server()
    assert asyncio.run(mcp.get_tool("evals_verify_record_pointer")) is not None
    brick = Path(__file__).parents[3] / "BRICK.yaml"
    assert "- evals_verify_record_pointer" in brick.read_text()


def test_semantically_invalid_correctly_rehashed_record_is_rejected() -> None:
    documents, invoker = _store()
    call = _tools(invoker)
    pointer = _record(call)["pointer"]
    document = documents[pointer["doc_id"]]
    document["pass_rate"] = 0.0
    document["content_hash"] = semantic_content_hash(document)
    rehashed_pointer = {**pointer, "content_hash": document["content_hash"]}

    result = _verify(call, rehashed_pointer)

    assert result["verified"] is False
    assert result["reason"] == "invalid_evaluation_run"


def test_real_storage_dto_tool_results_preserve_immutable_outcomes() -> None:
    documents: dict[str, dict] = {}

    def invoker(name: str, **kwargs):
        doc_id = kwargs["doc_id"]
        if name == "storage_doc_create_or_match":
            existing = documents.get(doc_id)
            if existing is None:
                documents[doc_id] = deepcopy(kwargs["data"])
                return ToolResult(data=DocCreateOrMatchOutput(
                    status="created", id=doc_id, collection=kwargs["collection"],
                    content_hash=kwargs["content_hash"],
                ))
            status = "matched" if existing["content_hash"] == kwargs["content_hash"] else "conflict"
            return ToolResult(data=DocCreateOrMatchOutput(
                status=status, id=doc_id, collection=kwargs["collection"],
                content_hash=kwargs["content_hash"],
                existing_content_hash=existing["content_hash"],
            ))
        if name == "storage_doc_get":
            data = documents.get(doc_id)
            return ToolResult(data=DocGetOutput(
                found=data is not None, id=doc_id, collection=kwargs["collection"], data=data,
            ))
        raise AssertionError(name)

    call = _tools(invoker)
    created = _record(call, timestamp="2026-07-01T00:00:00+00:00")
    matched = _record(call, timestamp="2026-07-01T00:00:00+00:00")
    conflict = _record(call, summary={"changed": True}, timestamp="2026-07-02T00:00:00+00:00")

    assert created["status"] == "created" and created["persisted"] is True
    assert matched["status"] == "matched" and matched["persisted"] is True
    assert conflict["status"] == "conflict" and conflict["persisted"] is False
    assert conflict["existing_content_hash"] == created["content_hash"]
    assert _verify(call, created["pointer"])["verified"] is True

    def unsupported(name: str, **kwargs):
        if name == "storage_doc_create_or_match":
            return ToolResult(data=DocCreateOrMatchOutput(
                status="unsupported", id=kwargs["doc_id"], collection=kwargs["collection"],
                content_hash=kwargs["content_hash"],
            ))
        raise AssertionError(name)

    rejected = _record(_tools(unsupported), run_id="unsupported", timestamp="2026-07-01T00:00:00+00:00")
    assert rejected["status"] == "unsupported"
    assert rejected["persisted"] is False


def test_verifier_rejects_failed_storage_tool_result() -> None:
    _, invoker = _store()
    pointer = _record(_tools(invoker))["pointer"]

    def failed(name: str, **kwargs):
        return ToolResult(ok=False, error="down") if name == "storage_doc_get" else invoker(name, **kwargs)

    assert _verify(_tools(failed), pointer)["reason"] == "storage_read_failed"
