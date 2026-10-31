"""Strict, hash-bound edge-model evaluation evidence tests."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from unittest.mock import patch

import pytest
from factory.evals.mcp import record_verification_tools, run_record_tools
from factory.evals.runtime.edge_model_evidence import EdgeModelEvidence
from factory.evals.runtime.run_record_contract import build_record, semantic_content_hash
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from hypothesis import given
from hypothesis import strategies as st

from .test_edge_model_evidence import (
    _edge_evidence,
    _record,
    _store,
    _tools,
    _verify,
)

@pytest.mark.parametrize(
    ("mutation", "expected_fragment"),
    [
        (lambda e: e["model"].update(digest="sha256:bad"), "digest"),
        (lambda e: e["dataset"]["split"].update(digest=""), "digest"),
        (lambda e: e["target"].update(fidelity="guess"), "fidelity"),
        (lambda e: e["runtime"].update(backend="mystery", unexpected=True), "runtime"),
        (lambda e: e["metrics"][0].update(value=float("nan")), "finite"),
        (
            lambda e: (
                e.update(metrics=e["metrics"][:1]),
                e.update(unavailable_measurements=[]),
            ),
            "task and resource",
        ),
    ],
)
def test_writer_rejects_invalid_edge_evidence_before_storage(mutation, expected_fragment):
    calls = []
    invoker = lambda name, **kwargs: calls.append((name, kwargs)) or {"status": "created"}
    call = _tools(invoker)
    evidence = _edge_evidence()
    mutation(evidence)

    result = _record(call, artifacts={"edge_model_evidence": evidence})

    assert result["persisted"] is False
    assert "edge_model_evidence" in result["reason"]
    assert expected_fragment in result["reason"]
    assert calls == []

def test_exact_pointer_rejects_edge_evidence_tamper_and_invalid_rehash():
    documents, invoker = _store()
    call = _tools(invoker)
    created = _record(call, artifacts={"edge_model_evidence": _edge_evidence()})
    pointer = created["pointer"]
    record = documents[pointer["doc_id"]]

    record["artifacts"]["edge_model_evidence"]["metrics"][0]["value"] = 0.1
    assert _verify(call, pointer)["reason"] == "tampered_record"

    record["artifacts"]["edge_model_evidence"] = _edge_evidence(
        model={"id": "tiny-audio-v1", "digest": "not-a-digest"},
    )
    record["content_hash"] = semantic_content_hash(record)
    changed_pointer = {**pointer, "content_hash": record["content_hash"]}
    assert _verify(call, changed_pointer)["reason"] == "invalid_edge_model_evidence"

def test_legacy_v2_record_without_edge_evidence_remains_readable_and_retries_match():
    _documents, invoker = _store()
    call = _tools(invoker)
    old_artifacts = {"schema_version": 1, "model_inputs": ["sealed://dataset"]}
    original = _record(call, run_id="legacy", timestamp="stable", artifacts=old_artifacts)
    retry = _record(call, run_id="legacy", timestamp="stable", artifacts=old_artifacts)

    assert retry["status"] == "matched"
    assert retry["content_hash"] == original["content_hash"]
    assert _verify(call, original["pointer"])["verified"] is True
