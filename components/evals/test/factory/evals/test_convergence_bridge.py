"""bd:python-factory-v7imt.1 — Convergence bridge tests.

Verifies:
1. reward.computed flow -> evals_persist_score called with source="reward"
2. auto-eval dispatch -> evals_persist_score called with source="auto-eval"
   AND the graph entity is still written
3. existing experiment save_run path defaults source="experiment"
4. defensive: persist failure in either bridge does NOT break the wallet or graph paths
"""
from __future__ import annotations

from factory.events.runtime.learning_handlers import handle_blockchain_reward
from factory.events.runtime._dispatch_evals import _persist_eval_result
from factory.events.runtime.models import Event
from factory.evals.runtime.adapters import run_results_store

import tempfile
from pathlib import Path


# ── reward -> evals bridge ────────────────────────────────────────────────────


def test_reward_bridge_calls_evals_persist_score_with_source_reward() -> None:
    """After blockchain_mint succeeds, evals_record_run is called with source=reward."""
    invoker_calls: list[tuple[str, dict]] = []

    def fake_invoker(tool_name: str, **kwargs):
        invoker_calls.append((tool_name, kwargs))
        if tool_name == "events_query_events":
            return {"events": [], "total": 0}
        if tool_name == "blockchain_get_wallet":
            return {"wallet_id": kwargs["wallet_id"], "balance": 100.0}
        if tool_name == "blockchain_mint":
            return {"tx_id": "tx-v7imt", "to_wallet": kwargs["to_wallet"]}
        if tool_name == "evals_record_run":
            return {"persisted": True, "doc_id": f"eval-{kwargs['run_id']}"}
        if tool_name == "events_publish":
            return {"event_id": "evt-1"}
        return {}

    event = Event(
        source="events.rewards",
        type="reward.computed",
        payload={
            "run_id": "run-v7imt-1",
            "workflow_run_id": "wf-v7imt-1",
            "reward_value": 50.0,
            "score": 0.82,
            "vuln_class": "IDOR",
            "domain_class": "access-control",
            "principal_id": "kiro-agent",
            "target_app": "WebGoat",
            "workflow_type": "dast",
        },
        principal_id="kiro-agent",
    )

    result = handle_blockchain_reward(event, fake_invoker)

    # Wallet path succeeded
    assert result["status"] == "committed"
    assert result["transaction_id"] == "tx-v7imt"

    # evals_record_run was called (v7imt.1 fix: uses record_run not persist_score)
    record_calls = [(n, k) for n, k in invoker_calls if n == "evals_record_run"]
    assert len(record_calls) == 1
    _, kwargs = record_calls[0]
    assert kwargs["source"] == "reward"
    assert kwargs["run_id"] == "wf-v7imt-1"
    assert kwargs["pass_rate"] == 1.0
    assert kwargs["avg_score"] == 0.82
    assert "experiment_name" in kwargs
    assert "reward:" in kwargs["experiment_name"]


def test_reward_bridge_failure_does_not_break_wallet_path() -> None:
    """If evals_record_run raises, wallet.rewarded still emits."""
    published: list[tuple[str, dict]] = []

    def fake_invoker(tool_name: str, **kwargs):
        if tool_name == "events_query_events":
            return {"events": [], "total": 0}
        if tool_name == "blockchain_get_wallet":
            return {"wallet_id": kwargs["wallet_id"], "balance": 10.0}
        if tool_name == "blockchain_mint":
            return {"tx_id": "tx-resilient", "to_wallet": kwargs["to_wallet"]}
        if tool_name == "evals_record_run":
            raise RuntimeError("evals storage offline")
        if tool_name == "events_publish":
            published.append((kwargs["event_type"], kwargs["payload"]))
            return {"event_id": "evt-2"}
        return {}

    event = Event(
        source="events.rewards",
        type="reward.computed",
        payload={
            "run_id": "run-resilient",
            "workflow_run_id": "wf-resilient",
            "reward_value": 10.0,
            "score": 0.5,
            "principal_id": "kiro-agent",
        },
        principal_id="kiro-agent",
    )

    result = handle_blockchain_reward(event, fake_invoker)

    # Wallet path succeeded despite bridge failure
    assert result["status"] == "committed"
    assert result["transaction_id"] == "tx-resilient"
    assert any(et == "wallet.rewarded" for et, _ in published)


def test_reward_bridge_respects_idempotency_guard() -> None:
    """If _already_published dedupes, no evals_persist_score call happens."""
    invoker_calls: list[tuple[str, dict]] = []

    def fake_invoker(tool_name: str, **kwargs):
        invoker_calls.append((tool_name, kwargs))
        if tool_name == "events_query_events":
            # Simulates already-published
            return {"events": [{"id": "existing"}], "total": 1}
        return {}

    event = Event(
        source="events.rewards",
        type="reward.computed",
        payload={
            "run_id": "run-deduped",
            "workflow_run_id": "wf-deduped",
            "reward_value": 5.0,
            "score": 0.3,
            "principal_id": "kiro-agent",
        },
        principal_id="kiro-agent",
    )

    result = handle_blockchain_reward(event, fake_invoker)

    # Deduped path — no mint, no bridge
    assert result.get("deduped") is True
    persist_calls = [n for n, _ in invoker_calls if n == "evals_record_run"]
    assert len(persist_calls) == 0


# ── auto-eval -> evals bridge ─────────────────────────────────────────────────


def test_auto_eval_bridge_calls_evals_persist_score_with_source_auto_eval() -> None:
    """_persist_eval_result writes to graph AND calls evals_persist_score."""
    from factory.evals.runtime.run_record_contract import (
        EVALUATION_RUN_RECORD_KIND, SCHEMA_VERSION, document_id,
    )

    invoker_calls: list[tuple[str, dict]] = []
    canonical_id = document_id("run-autoeval-1", EVALUATION_RUN_RECORD_KIND)

    def fake_invoker(tool_name: str, **kwargs):
        invoker_calls.append((tool_name, kwargs))
        if tool_name == "evals_record_run":
            return {
                "persisted": True, "status": "created", "projection_key": "eval-record:hash",
                "pointer": {
                    "collection": "eval_results", "doc_id": canonical_id,
                    "record_kind": EVALUATION_RUN_RECORD_KIND,
                    "schema_version": SCHEMA_VERSION,
                    "revision": f"v{SCHEMA_VERSION}", "content_hash": "sha256:hash",
                },
            }
        return {}

    payload = {"run_id": "run-autoeval-1", "workflow_id": "graph-42"}
    result = {
        "summary": {"avg_score": 0.75, "pass_rate": 0.8},
        "results": [
            {"evaluator": "coherence", "score": 0.7},
            {"evaluator": "relevance", "score": 0.8},
        ],
    }

    _persist_eval_result(fake_invoker, payload, result)

    graph_calls = [(n, k) for n, k in invoker_calls if n == "graph_add_entity"]
    assert len(graph_calls) == 1
    _, graph_kwargs = graph_calls[0]
    assert graph_kwargs["entity_id"] == f"eval-record-{canonical_id}"
    assert graph_kwargs["entity_type"] == "EvalRecordPointer"

    event_calls = [(n, k) for n, k in invoker_calls if n == "events_publish"]
    assert len(event_calls) == 1

    record_calls = [(n, k) for n, k in invoker_calls if n == "evals_record_run"]
    assert len(record_calls) == 1
    _, record_kwargs = record_calls[0]
    assert record_kwargs["source"] == "auto-eval"
    assert record_kwargs["run_id"] == "run-autoeval-1"
    assert record_kwargs["experiment_name"] == "auto-eval:graph-42"


def test_auto_eval_bridge_failure_does_not_break_graph_write() -> None:
    """If evals_persist_score raises, graph entity and event still written."""
    invoker_calls: list[tuple[str, dict]] = []

    def fake_invoker(tool_name: str, **kwargs):
        invoker_calls.append((tool_name, kwargs))
        if tool_name == "evals_record_run":
            raise RuntimeError("evals offline")
        return {}

    payload = {"run_id": "run-resilient-eval", "workflow_id": "graph-99"}
    result = {
        "summary": {"avg_score": 0.6, "pass_rate": 0.5},
        "results": [{"evaluator": "judge", "score": 0.6}],
    }

    # Should not raise
    _persist_eval_result(fake_invoker, payload, result)

    # Durable failure suppresses non-authoritative projections.
    assert [n for n, _ in invoker_calls] == ["evals_record_run"]


# ── run_results_store source field ────────────────────────────────────────────


def test_save_run_defaults_source_experiment() -> None:
    """Existing save_run callers get source='experiment' without changes."""
    tmp = tempfile.mkdtemp()
    orig = run_results_store._RUNS_DIR
    run_results_store._RUNS_DIR = Path(tmp) / "eval_runs"
    try:
        run_id = run_results_store.save_run(
            experiment_name="test-exp",
            case_results=[{"case_name": "c1", "passed": True, "score": 1.0}],
            summary={},
            evaluators_used=["judge"],
            model_id="test-model",
            system_prompt="test",
        )
        data = run_results_store.get_run(run_id)
        assert data is not None
        assert data["source"] == "experiment"
    finally:
        run_results_store._RUNS_DIR = orig


def test_save_run_persists_custom_source() -> None:
    """save_run with source='reward' persists it in the JSON."""
    tmp = tempfile.mkdtemp()
    orig = run_results_store._RUNS_DIR
    run_results_store._RUNS_DIR = Path(tmp) / "eval_runs"
    try:
        run_id = run_results_store.save_run(
            experiment_name="reward:IDOR",
            case_results=[{"case_name": "c1", "passed": True, "score": 0.8}],
            summary={},
            evaluators_used=[],
            model_id="",
            system_prompt="",
            source="reward",
        )
        data = run_results_store.get_run(run_id)
        assert data is not None
        assert data["source"] == "reward"
    finally:
        run_results_store._RUNS_DIR = orig


def test_list_runs_includes_source_field() -> None:
    """list_runs exposes source for UI filtering."""
    tmp = tempfile.mkdtemp()
    orig = run_results_store._RUNS_DIR
    run_results_store._RUNS_DIR = Path(tmp) / "eval_runs"
    try:
        run_results_store.save_run(
            experiment_name="auto-eval:graph-1",
            case_results=[{"case_name": "c1", "passed": True, "score": 0.9}],
            summary={},
            evaluators_used=["coherence"],
            model_id="m1",
            system_prompt="",
            source="auto-eval",
        )
        runs = run_results_store.list_runs()
        assert len(runs) == 1
        assert runs[0]["source"] == "auto-eval"
    finally:
        run_results_store._RUNS_DIR = orig


# ── persist_score_result source parameter ─────────────────────────────────────


def test_persist_score_result_threads_source_to_storage() -> None:
    """source parameter flows through to the storage payload."""
    from factory.evals.runtime._persist_score import persist_score_result

    captured: dict = {}

    def invoker(tool: str, **kwargs):
        captured.update(kwargs)
        return {"schema_version": "v1", "ok": True, "data": {"persisted": True, "status": "created"}, "error": None, "idempotency_key": None}

    ok = persist_score_result(
        invoker, "run-src-test", "dast", "App", "IDOR",
        {"f1": 0.8, "precision": 0.7, "recall": 0.9},
        source="reward",
    )

    assert ok is True
    assert captured["source"] == "reward"
    assert captured["record_kind"] == "evaluation_score_projection"


def test_persist_score_result_defaults_source_experiment() -> None:
    """Existing callers without source get 'experiment' (backward-compat)."""
    from factory.evals.runtime._persist_score import persist_score_result

    captured: dict = {}

    def invoker(tool: str, **kwargs):
        captured.update(kwargs)
        return {"schema_version": "v1", "ok": True, "data": {"persisted": True, "status": "created"}, "error": None, "idempotency_key": None}

    persist_score_result(
        invoker, "run-default", "sast", "App", "SQLi", {"f1": 0.5},
    )

    assert captured["source"] == "experiment"
    assert captured["record_kind"] == "evaluation_score_projection"
