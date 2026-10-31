from __future__ import annotations

import asyncio
from copy import deepcopy
from unittest.mock import patch

from hypothesis import given, strategies as st

from factory.evals.mcp import record_verification_tools, review_tools, run_record_tools
from factory.evals.runtime.review_record import decide_review
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog


def _rows(passed: int, total: int, score: float) -> list[dict]:
    return [
        {
            "evaluator": f"criterion-{index}", "score": score,
            "test_pass": index < passed, "reason": "evidence",
        }
        for index in range(total)
    ]


def test_review_threshold_allows_policy_pass_without_all_rows_passing() -> None:
    decision = decide_review(
        "run-threshold", "review-qa", "a" * 64,
        _rows(4, 5, 0.8), {"model": "test"},
    )
    assert decision.verdict == "PASS"
    assert decision.pass_rate == 0.8 and decision.avg_score == 0.8
    assert decision.request["reviewer_tool_scope"] == [
        "devtools_read_file", "devtools_list_dir", "devtools_search",
        "devtools_git_status", "devtools_git_diff", "devtools_git_log",
    ]


@given(
    pass_count=st.integers(min_value=0, max_value=5),
    score=st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False),
)
def test_review_verdict_is_exact_threshold_function(pass_count: int, score: float) -> None:
    decision = decide_review(
        "run-property", "review-meta", "b" * 64,
        _rows(pass_count, 5, score), {},
    )
    expected = "PASS" if pass_count / 5 >= 0.8 and score >= 0.75 else "FAIL"
    assert decision.verdict == expected


def test_review_record_is_immutable_retryable_and_pointer_verified() -> None:
    catalog = ToolCatalog("review-record-test")
    run_record_tools.register(catalog)
    review_tools.register(catalog)
    record_verification_tools.register(catalog)
    documents: dict[str, dict] = {}

    def invoker(name: str, **kwargs):
        if name == "evals_record_run":
            return asyncio.run(catalog.get_tool(name)).fn(**kwargs)
        if name == "storage_doc_create_or_match":
            doc_id = kwargs["doc_id"]
            existing = documents.get(doc_id)
            if existing is None:
                documents[doc_id] = deepcopy(kwargs["data"])
                return {"status": "created"}
            status = "matched" if existing["content_hash"] == kwargs["content_hash"] else "conflict"
            return {
                "status": status,
                "existing_content_hash": existing["content_hash"],
            }
        if name == "storage_doc_get":
            data = documents.get(kwargs["doc_id"])
            return {
                "collection": kwargs["collection"], "id": kwargs["doc_id"],
                "data": deepcopy(data),
            }
        raise AssertionError(name)

    review = asyncio.run(catalog.get_tool("evals_review_and_record")).fn
    request = {
        "run_id": "review-run", "policy_id": "review-qa",
        "manifest_digest": "c" * 64, "rows": _rows(4, 5, 0.8),
        "agent": {"model": "test"},
    }
    with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
        first = review(**request)
        second = review(**request)
        verify = asyncio.run(catalog.get_tool("evals_verify_record_pointer")).fn(
            **first.data.record.pointer,
        )
    assert first.ok and second.ok
    assert first.data.verdict == "PASS"
    assert first.data.record.content_hash == second.data.record.content_hash
    stored = documents[first.data.record.doc_id]
    assert stored["policy_ref"]["manifest_digest"] == "c" * 64
    assert stored["rubric_digest"] and stored["reviewer_tool_scope"]
    assert verify.ok and verify.data.verified is True, verify.data.reason
    assert verify.data.policy_ref["policy_id"] == "review-qa"
    assert verify.data.reviewer_tool_scope == stored["reviewer_tool_scope"]
    assert verify.data.rubric_digest == stored["rubric_digest"]


def test_review_tool_has_strict_typed_boundary() -> None:
    catalog = ToolCatalog("review-contract")
    review_tools.register(catalog)
    tool = asyncio.run(catalog.get_tool("evals_review_and_record")).fn
    assert getattr(tool, "_mcp_category") == "operational"
    assert getattr(tool, "_mcp_input_model").model_config["extra"] == "forbid"
    assert getattr(tool, "_mcp_output_model").model_config["extra"] == "forbid"
