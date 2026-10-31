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


def _tools(invoker):
    mcp = ToolCatalog("edge-model-evidence")
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
            current = documents[key]["content_hash"]
            requested = kwargs["data"]["content_hash"]
            return {
                "status": "matched" if current == requested else "conflict",
                "existing_content_hash": current,
            }
        if name == "storage_doc_get":
            if key not in documents:
                return {"error": "not_found", "collection": kwargs["collection"], "id": key}
            return {"collection": kwargs["collection"], "id": key, "data": deepcopy(documents[key])}
        raise AssertionError(name)

    return documents, invoker


def _record(call, **extra):
    request = {
        "run_id": "edge-run", "experiment_name": "edge-exp", "verdict": "PASS",
        "pass_rate": 1.0, "avg_score": 1.0, "total_cases": 1, "passed": 1,
        "case_results": [{"passed": True, "score": 1.0}], "case_scores": [1.0],
        "summary": {"stable": True}, **extra,
    }
    return call("evals_record_run", **request)


def _verify(call, pointer):
    return call("evals_verify_record_pointer", **pointer)


def _edge_evidence(**changes):
    evidence = {
        "schema_version": 1,
        "model": {"id": "tiny-audio-v1", "digest": "sha256:" + "a" * 64},
        "dataset": {
            "id": "sensor-failure-v1", "digest": "sha256:" + "b" * 64,
            "split": {"name": "test", "digest": "sha256:" + "c" * 64},
        },
        "evaluator": {
            "id": "sensor-failure-evaluator", "version": "1.0",
            "digest": "sha256:" + "d" * 64,
        },
        "policy": {"id": "edge-sensor-v1", "digest": "sha256:" + "e" * 64},
        "target": {
            "platform": "ios", "device_class": "phone", "device_model": "iPhone 15",
            "fidelity": "native_simulator",
        },
        "runtime": {"name": "core-ml", "version": "17.0", "backend": "cpu"},
        "metrics": [
            {"name": "macro_f1", "category": "task", "value": 0.91, "unit": "ratio"},
            {"name": "inference_latency", "category": "resource", "value": 12.5, "unit": "ms"},
        ],
        "unavailable_measurements": [
            {
                "name": "energy", "category": "resource",
                "reason": "simulator does not expose power telemetry",
            },
        ],
    }
    evidence.update(changes)
    return evidence


def test_validated_measurements_are_immutable_and_keep_json_array_contract():
    source = _edge_evidence()
    evidence = EdgeModelEvidence.model_validate(source)

    source["metrics"].append(deepcopy(source["metrics"][0]))
    source["unavailable_measurements"].clear()

    assert isinstance(evidence.metrics, tuple)
    assert isinstance(evidence.unavailable_measurements, tuple)
    assert len({(item.category, item.name) for item in evidence.metrics}) == len(evidence.metrics)
    assert {item.category for item in evidence.metrics + evidence.unavailable_measurements} == {
        "task", "resource",
    }
    with pytest.raises(AttributeError):
        evidence.metrics.append(evidence.metrics[0])
    with pytest.raises(AttributeError):
        evidence.unavailable_measurements.clear()

    serialized = evidence.model_dump(mode="json")
    assert isinstance(serialized["metrics"], list)
    assert isinstance(serialized["unavailable_measurements"], list)
    assert serialized["metrics"] == _edge_evidence()["metrics"]
    assert serialized["unavailable_measurements"] == _edge_evidence()["unavailable_measurements"]


def test_edge_evidence_is_validated_returned_and_bound_to_immutable_hash():
    documents, invoker = _store()
    call = _tools(invoker)
    request = {
        "timestamp": "stable",
        "artifacts": {"schema_version": 1, "edge_model_evidence": _edge_evidence()},
    }
    first = _record(call, **request)
    retry = _record(call, **request)
    result = _verify(call, first["pointer"])

    assert first["persisted"] is True
    assert retry["status"] == "matched"
    assert retry["content_hash"] == first["content_hash"]
    assert result["verified"] is True
    assert result["edge_model_evidence"] == _edge_evidence()
    _, unchanged = build_record(
        run_id="same-run", record_kind="evaluation_run", terminal_state="completed",
        timestamp="stable", payload={"artifacts": {"edge_model_evidence": _edge_evidence()}},
    )
    _, changed = build_record(
        run_id="same-run", record_kind="evaluation_run", terminal_state="completed",
        timestamp="stable", payload={"artifacts": {"edge_model_evidence": _edge_evidence(
            metrics=[{"name": "macro_f1", "category": "task", "value": 0.92, "unit": "ratio"},
                     {"name": "inference_latency", "category": "resource",
                      "value": 12.5, "unit": "ms"}],
        )}},
    )
    assert changed["content_hash"] != unchanged["content_hash"]
    stored = documents[first["pointer"]["doc_id"]]
    assert stored["artifacts"]["edge_model_evidence"] == _edge_evidence()


@given(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
def test_any_finite_metric_value_is_authenticated(value: float):
    base = _edge_evidence()
    base["metrics"][0]["value"] = value
    changed = _edge_evidence()
    changed["metrics"][0]["value"] = value / 2.0

    _, first = build_record(
        run_id="property-run", record_kind="evaluation_run", terminal_state="completed",
        timestamp="stable", payload={"artifacts": {"edge_model_evidence": base}},
    )
    _, second = build_record(
        run_id="property-run", record_kind="evaluation_run", terminal_state="completed",
        timestamp="stable", payload={"artifacts": {"edge_model_evidence": changed}},
    )

    if value != value / 2.0:
        assert first["content_hash"] != second["content_hash"]
