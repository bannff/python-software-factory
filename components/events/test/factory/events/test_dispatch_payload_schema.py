"""Snapshot + roundtrip tests for the canonical learning events.

Wave 0 (bd python-factory-wosz) + bd python-factory-o7t8 (learning.applied).
Pydantic models in ``learning_contracts.LEARNING_EVENT_MODELS`` validate at
the ``validate_learning_payload`` call inside each handler; this file pins
the observed publish shape so a future refactor is caught.
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from factory.events.runtime.learning_contracts import (
    LEARNING_EVENT_MODELS,
    ConvergenceCheckedPayload,
    MemoryLearningStoredPayload,
    RewardComputedPayload,
    WalletRewardedPayload,
    validate_learning_payload,
)
from factory.events.runtime.learning_handlers import (
    handle_blockchain_reward,
    handle_convergence_check,
    handle_memory_learning,
)
from factory.events.runtime.models import Event
from factory.events.runtime.rewards_handler import handle_rewards_process
from factory.blockchain.mcp.contracts.deterministic import GetWalletOutput
from factory.blockchain.mcp.contracts.ledger import TransactionOutput
from factory.mcp_utils.interface import ToolResult, ok, set_service
from factory.memory.mcp.contracts.operational import MemoryStoreOutput
from factory.metrics.mcp.contracts.operational import DriftOutput, RecordOutput
# Golden required-keys per learning event. THIS dict is the contract.
EXPECTED_LEARNING_REQUIRED_KEYS: dict[str, frozenset[str]] = {
    "reward.computed": frozenset({"run_id", "workflow_run_id", "idempotency_key"}),
    "wallet.rewarded": frozenset(
        {"run_id", "workflow_run_id", "wallet_id", "idempotency_key"}),
    "memory.learning_stored": frozenset(
        {"run_id", "workflow_run_id", "summary_type", "idempotency_key"}),
    "convergence.checked": frozenset(
        {"run_id", "workflow_run_id", "metric_id", "converged",
         "baseline_window", "comparison_window"}),
    "learning.applied": frozenset({"run_id", "workflow_run_id", "idempotency_key"}),
    "workflow.improvement": frozenset({"run_id", "workflow_run_id", "idempotency_key"}),
}
def test_learning_event_set_is_exactly_six() -> None:
    """Guard: adding a new contracted event must be deliberate."""
    assert set(LEARNING_EVENT_MODELS.keys()) == set(EXPECTED_LEARNING_REQUIRED_KEYS)


@pytest.mark.parametrize("event_type", list(EXPECTED_LEARNING_REQUIRED_KEYS))
def test_required_keys_match_golden_snapshot(event_type: str) -> None:
    model = LEARNING_EVENT_MODELS[event_type]
    actual = frozenset(model.model_json_schema().get("required", []))
    assert actual == EXPECTED_LEARNING_REQUIRED_KEYS[event_type]


# -- Behavioral snapshot — observed publish payloads ----------------------

def _payload(**overrides):
    base = {
        "run_id": "run-x", "workflow_run_id": "wf-x",
        "graph_id": "g1", "target_app": "WebGoat",
        "workflow_type": "dast", "vuln_class": "IDOR",
        "score": 0.82, "precision": 0.8, "recall": 0.84,
        "true_positives": 4, "false_positives": 1, "false_negatives": 2,
        "reward_value": 12,
    }
    base.update(overrides)
    return base


def _captured_publish(handler, event, extras=None):
    """Run handler with fake invoker, return [(event_type, payload), ...]."""
    published: list[tuple[str, dict]] = []
    extras = extras or {}
    set_service("tool_invoker_for_caller",
                lambda caller: lambda target, **call: fake_invoker("events_publish", **call["arguments"]))

    def fake_invoker(tool_name, **kwargs):
        if tool_name == "events_query_events":
            return {"events": [], "total": 0}
        if tool_name == "events_publish":
            published.append((kwargs["event_type"], kwargs["payload"]))
            return {"event_id": f"evt-{len(published)}", "status": "ok"}
        if tool_name == "blockchain_get_wallet": return ToolResult(data=GetWalletOutput(wallet_id=kwargs["wallet_id"], owner_id="agent", balance=0, created_at=""))
        if tool_name == "blockchain_mint": return ToolResult(data=TransactionOutput(tx_id="tx-1", tx_type="mint", to_wallet=kwargs["to_wallet"], amount=12, memo="", status="committed"))
        return extras.get(tool_name, {"ok": True})

    handler(event, fake_invoker)
    return published


def _assert_pub(published, expected_type):
    assert len(published) == 1
    et, payload = published[0]
    assert et == expected_type
    assert frozenset(payload) >= EXPECTED_LEARNING_REQUIRED_KEYS[et]
    out = validate_learning_payload(et, payload)
    return out


def test_reward_computed_publish_shape(monkeypatch) -> None:
    monkeypatch.setattr(
        "factory.events.runtime.rewards_handler._run_rl_loop",
        lambda *a, **kw: {
            "source_id": "gt-findings",
            "scoring": {"f1": 0.82, "precision": 0.8, "recall": 0.84,
                        "true_positives": 4, "false_positives": 1,
                        "false_negatives": 2},
            "blockchain": {"amount": 82.0, "wallet_id": "wallet-kiro-agent"},
        },
    )
    event = Event(source="agent.graph", type="graph.completed",
                  payload={"run_id": "run-z", "graph_id": "g1",
                           "execution_time": 1.25})
    out = _assert_pub(
        _captured_publish(handle_rewards_process, event), "reward.computed")
    assert out["run_id"] == "run-z"


def test_wallet_rewarded_publish_shape() -> None:
    event = Event(source="events.rewards", type="reward.computed",
                  payload=_payload())
    out = _assert_pub(
        _captured_publish(
            handle_blockchain_reward, event,
            extras={"blockchain_mint": {"tx_id": "tx-1",
                                        "to_wallet": "wallet-kiro-agent"}}),
        "wallet.rewarded")
    assert out["wallet_id"] and out["idempotency_key"]


def test_memory_learning_stored_publish_shape() -> None:
    event = Event(source="events.rewards", type="reward.computed",
                  payload=_payload())
    out = _assert_pub(
        _captured_publish(
            handle_memory_learning, event,
            extras={"memory_memory_store": ToolResult(data=MemoryStoreOutput(
                stored=True,
                memory={"id": "mem-1", "user_id": "kiro-agent", "content": "fact",
                        "memory_type": "long_term", "category": "fact", "metadata": {},
                        "relevance_score": 1.0, "created_at": "2026-01-01T00:00:00Z"},
            ))}),
        "memory.learning_stored")
    assert out["summary_type"] == "workflow_rl"


def test_convergence_checked_publish_shape() -> None:
    event = Event(source="events.rewards", type="reward.computed", payload=_payload())
    out = _assert_pub(
        _captured_publish(
            handle_convergence_check, event,
            extras={
                "metrics_record": ok(RecordOutput(ok=True, metric_id="pipeline-f1", value=0.0, timestamp=1.0)),
                "metrics_detect_drift": ok(DriftOutput(metric_id="pipeline-f1", drifted=False)),
            }),
        "convergence.checked")
    assert out["metric_id"] == "pipeline-f1"
    assert out["baseline_window"] == "7d"
    assert out["comparison_window"] == "24h"


# -- Hypothesis: validate_learning_payload roundtrips for valid inputs -----

_id = st.text(min_size=1, max_size=20,
              alphabet=st.characters(whitelist_categories=("L", "N")))


@settings(max_examples=50)
@given(run_id=_id, wf=_id, idem=_id,
       score=st.floats(min_value=0, max_value=1, allow_nan=False))
def test_reward_computed_roundtrips(run_id, wf, idem, score):
    p = RewardComputedPayload(run_id=run_id, workflow_run_id=wf,
                              idempotency_key=idem, score=score)
    out = validate_learning_payload("reward.computed", p.model_dump())
    assert out["run_id"] == run_id and out["score"] == score


@settings(max_examples=50)
@given(run_id=_id, wf=_id, idem=_id, wallet=_id,
       reward=st.floats(min_value=0, max_value=10000, allow_nan=False))
def test_wallet_rewarded_roundtrips(run_id, wf, idem, wallet, reward):
    p = WalletRewardedPayload(run_id=run_id, workflow_run_id=wf,
                              idempotency_key=idem, wallet_id=wallet,
                              reward_value=reward)
    out = validate_learning_payload("wallet.rewarded", p.model_dump())
    assert out["wallet_id"] == wallet


@settings(max_examples=50)
@given(run_id=_id, wf=_id, idem=_id,
       summary=st.sampled_from(["workflow_rl", "graph_rl", "swarm_rl"]))
def test_memory_learning_stored_roundtrips(run_id, wf, idem, summary):
    p = MemoryLearningStoredPayload(run_id=run_id, workflow_run_id=wf,
                                    idempotency_key=idem, summary_type=summary)
    out = validate_learning_payload("memory.learning_stored", p.model_dump())
    assert out["summary_type"] == summary


@settings(max_examples=50)
@given(run_id=_id, wf=_id, metric=_id, converged=st.booleans(),
       recorded=st.integers(min_value=0, max_value=10))
def test_convergence_checked_roundtrips(run_id, wf, metric, converged, recorded):
    p = ConvergenceCheckedPayload(run_id=run_id, workflow_run_id=wf,
                                  metric_id=metric, converged=converged,
                                  baseline_window="7d", comparison_window="24h",
                                  metrics_recorded=recorded)
    out = validate_learning_payload("convergence.checked", p.model_dump())
    assert out["converged"] is converged
    assert out["metrics_recorded"] == recorded
