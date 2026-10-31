"""Property and source-contract tests for the ML Observatory."""
from __future__ import annotations

from unittest.mock import patch

from hypothesis import given, settings, strategies as st

from factory.machine_learning.runtime.observatory_lineage import MAX_NODES, build_lineage
from factory.machine_learning.runtime.observatory_projection import build_summary
from factory.machine_learning.runtime.observatory_sources import (
    load_fine_tuning_jobs,
    load_learning_runs,
    load_training_receipts,
)
from factory.mcp_utils.interface import ToolResult
from factory.storage.mcp.contracts.operational import DocumentData, DocFindOutput


def _source(name, value, health="healthy"):
    return {"name": name, "value": value, "health": health, "durability": "test", "freshness": "now", "error": None}


def _sources(training, learning):
    return [
        _source("training_receipts", training, "error" if training is None else "healthy"),
        _source("learning_runs", learning, "error" if learning is None else "healthy"),
        _source("fine_tuning_jobs", []),
        _source("live_models", None, "degraded"),
    ]


def _receipt(run_id="run-1", path="/tmp/model"):
    return {
        "run_id": run_id, "experiment_name": "exp", "model_type": "lightgbm",
        "metrics": {"auroc": 0.8}, "model_path": path,
        "timestamp": f"2026-01-{int(run_id.split('-')[-1]) % 28 + 1:02d}T00:00:00Z",
    }


@settings(max_examples=50)
@given(
    training_available=st.booleans(), learning_available=st.booleans(),
    training_count=st.integers(min_value=0, max_value=3),
    learning_count=st.integers(min_value=0, max_value=3),
)
def test_population_truth_table(training_available, learning_available, training_count, learning_count):
    training = [_receipt(f"run-{i + 1}") for i in range(training_count)] if training_available else None
    learning = [{"run_id": f"learn-{i}"} for i in range(learning_count)] if learning_available else None
    summary = build_summary(_sources(training, learning))
    assert summary["overview"]["training_runs"] == (training_count if training_available else None)
    assert summary["overview"]["learning_runs"] == (learning_count if learning_available else None)
    if not training_available or not learning_available:
        assert summary["population_state"] is None
    else:
        expected = (
            "mixed" if training_count and learning_count else
            "training_only" if training_count else
            "learning_only" if learning_count else "empty"
        )
        assert summary["population_state"] == expected


def test_raw_receipts_use_exact_call_and_keep_valid_records_when_degraded():
    calls = []

    def invoker(tool_name, **kwargs):
        calls.append((tool_name, kwargs))
        return {"documents": [{"data": _receipt()}, {"data": {"run_id": "bad"}}]}

    with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
        source = load_training_receipts()
    assert calls == [("storage_doc_find", {"collection": "ml_training_runs", "query": {}, "limit": 500})]
    assert source["health"] == "degraded"
    assert [row["run_id"] for row in source["value"]] == ["run-1"]
    assert "skipped 1" in source["error"]


@settings(max_examples=50)
@given(result=st.sampled_from([None, [], {}, {"documents": "bad"}, {"error": "down", "documents": []}]))
def test_malformed_top_level_receipt_results_are_unavailable(result):
    with patch("factory.mcp_utils.registry._services", {"tool_invoker": lambda *a, **k: result}):
        source = load_training_receipts()
    assert source["value"] is None
    assert source["health"] == "error"


def test_models_deduplicate_by_artifact_without_canonical_id():
    duplicate_old = _receipt("run-1", "/tmp/shared")
    duplicate_new = _receipt("run-2", "/tmp/shared")
    summary = build_summary(_sources([duplicate_old, duplicate_new], []))
    assert len(summary["models"]) == 1
    assert summary["models"][0]["entity_id"] is None
    assert summary["models"][0]["source_run_id"] == "run-2"


def test_lineage_is_evidence_only_and_bounded_without_dangling_edges():
    receipts = [_receipt(f"run-{i + 1}", f"/tmp/model-{i}") for i in range(60)]
    learning = [{
        "run_id": "learn-1", "workflow_run_id": "wf-1", "graph_id": "graph-1",
        "reward_event_id": "reward-1", "wallet_event_id": "wallet-1",
        "transaction_id": "tx-1", "event_history": [{"event_id": "reward-1"}],
    }]
    lineage = build_lineage(receipts, learning)
    node_ids = {node["node_id"] for node in lineage["nodes"]}
    assert len(node_ids) == MAX_NODES
    assert lineage["truncated"] is True
    assert all(edge["source"] in node_ids and edge["target"] in node_ids for edge in lineage["edges"])
    assert not any(edge["source"] == "event:reward-1" and edge["target"] == "event:wallet-1" for edge in lineage["edges"])
    assert lineage["missing_links"]


def test_learning_source_preserves_downstream_failure_as_unavailable():
    def broken_invoker(tool_name, **kwargs):
        raise RuntimeError(f"{tool_name} unavailable")

    with patch("factory.mcp_utils.registry._services", {"tool_invoker": broken_invoker}):
        source = load_learning_runs()
    assert source["value"] is None
    assert source["health"] == "error"
    assert "events_query_events unavailable" in source["error"]


def test_fine_tuning_source_uses_injected_runtime_supplier():
    calls = []

    class FineTuner:
        def list_jobs(self):
            calls.append("list_jobs")
            return []

    class Runtime:
        def get_finetuner(self):
            calls.append("get_finetuner")
            return FineTuner()

    source = load_fine_tuning_jobs(Runtime)
    assert calls == ["get_finetuner", "list_jobs"]
    assert source["value"] == []
    assert source["health"] == "healthy"


def test_graph_identity_requires_explicit_graph_event_evidence():
    lineage = build_lineage([], [{
        "workflow_run_id": "wf-1", "graph_id": "graph-1",
        "reward_event_id": "reward-1", "domain_class": "probe",
        "event_history": [{"event_id": "reward-1"}],
    }])
    node_ids = {node["node_id"] for node in lineage["nodes"]}
    assert "event:reward-1" in node_ids
    assert "graph:graph-1" not in node_ids
    workflow = next(node for node in lineage["nodes"] if node["node_id"] == "workflow-run:wf-1")
    assert workflow["domain_metadata"] == {"domain_class": "probe"}


def test_training_receipts_accept_real_storage_tool_results() -> None:
    successful = ToolResult(data=DocFindOutput(documents=[DocumentData(id="run-1", data=_receipt())]))
    with patch("factory.mcp_utils.registry._services", {"tool_invoker": lambda *_args, **_kwargs: successful}):
        source = load_training_receipts()
    assert source["health"] == "healthy"
    assert [receipt["run_id"] for receipt in source["value"]] == ["run-1"]

    failed = ToolResult(ok=False, error="storage unavailable")
    with patch("factory.mcp_utils.registry._services", {"tool_invoker": lambda *_args, **_kwargs: failed}):
        source = load_training_receipts()
    assert source["health"] == "error"
    assert source["value"] is None
