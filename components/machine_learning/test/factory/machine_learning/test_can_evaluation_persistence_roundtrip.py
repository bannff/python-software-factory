"""Real Evals persistence-to-ML adequacy verification round trip."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from unittest.mock import patch

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from factory.evals.mcp import record_verification_tools, run_record_tools
from factory.machine_learning.runtime.can_evaluation_policy import derive_case, derive_run
from factory.machine_learning.runtime.can_evals_binding import verify_evaluation_records

from .test_can_evaluation_binding import EVIDENCE, GOOD, PROVENANCE


def test_exact_aggregates_survive_evals_persistence_and_ml_verification():
    documents = {}

    def storage(name, **kwargs):
        if name == "storage_doc_create_or_match":
            documents[kwargs["doc_id"]] = deepcopy(kwargs["data"])
            return {"status": "created"}
        if name == "storage_doc_get":
            return {
                "collection": kwargs["collection"], "id": kwargs["doc_id"],
                "data": deepcopy(documents[kwargs["doc_id"]]),
            }
        raise AssertionError(name)

    server = ToolCatalog("evals-roundtrip")
    run_record_tools.register(server)
    record_verification_tools.register(server)

    def call(name, **kwargs):
        with patch("factory.mcp_utils.registry._services", {"tool_invoker": storage}):
            return asyncio.run(server.call_tool(name, kwargs)).structured_content

    scores = (0.6111, 0.7222, 0.8333)
    cases = tuple(derive_case(
        case_id=f"0x{index}", model_id=f"model-{index}",
        metrics={**GOOD, "f1": score}, evidence=EVIDENCE,
        provenance=PROVENANCE,
    ) for index, score in enumerate(scores, start=1))
    adequacy = derive_run(cases)
    raw = adequacy.model_dump(mode="json")
    persisted_envelope = call(
        "evals_record_run", run_id="exact-aggregates", experiment_name="exact",
        verdict=adequacy.verdict, pass_rate=adequacy.pass_rate,
        avg_score=adequacy.avg_score, total_cases=adequacy.total_cases,
        passed=adequacy.passed, failed_cases=adequacy.failed,
        case_results=raw["cases"], case_scores=[case.score for case in cases],
        evaluators_used=["evals.can-model@v1"], summary={"adequacy": raw},
    )

    assert persisted_envelope["ok"] is True
    persisted = persisted_envelope["data"]
    verified = verify_evaluation_records(call, [persisted["pointer"]])[0]

    assert persisted["persisted"] is True
    assert verified.adequacy == adequacy
    assert documents[persisted["doc_id"]]["avg_score"] == adequacy.avg_score
