"""Hypothesis property + consumer dual-emit tests for the alias compat layer.

bd python-factory-col2. ``LearningEventPayload`` accepts both ``graph_id``
and ``workflow_id``: a pre-validator backfills whichever is missing and
rejects mismatched values. These tests pin the four invariants from the
approved design (memory id 3a696d55-7d92-42d4-869a-0ec84d347067):

  (i)   graph_id only        -> output has both keys, equal
  (ii)  workflow_id only     -> output has both keys, equal
  (iii) both present, equal  -> validates unchanged
  (iv)  both present, differ -> ValidationError raised

The "Consumer triples" section asserts the same dual-emit guarantee across
each downstream handler (rewards, blockchain, memory, convergence) so the
contract holds end-to-end through the publish boundary.
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st
from pydantic import ValidationError

from factory.events.runtime.learning_contracts import (
    LearningEventPayload,
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
from factory.memory.mcp.contracts.base import MemoryData
from factory.memory.mcp.contracts.operational import MemoryStoreOutput
from factory.metrics.mcp.contracts.operational import DriftOutput, RecordOutput


def _stored_memory(memory_id: str = "mem-1") -> ToolResult[MemoryStoreOutput]:
    return ToolResult(data=MemoryStoreOutput(stored=True, memory=MemoryData(
        id=memory_id, user_id="kiro-agent", content="fact", memory_type="long_term",
        category="fact", metadata={}, relevance_score=1.0, created_at="2026-01-01T00:00:00Z")))

# -- Strategy + helpers -----------------------------------------------------

_id = st.text(min_size=1, max_size=24,
              alphabet=st.characters(whitelist_categories=("L", "N"),
                                     whitelist_characters="-_"))
_run = st.text(min_size=1, max_size=24,
               alphabet=st.characters(whitelist_categories=("L", "N")))


def _build(**kw):
    base = {"run_id": "r", "workflow_run_id": "wf"}
    base.update(kw)
    return LearningEventPayload(**base)


# -- Hypothesis properties --------------------------------------------------

@settings(max_examples=80)
@given(gid=_id)
def test_graph_id_only_backfills_workflow_id(gid):
    """(i) graph_id only -> both keys equal on output."""
    d = _build(graph_id=gid).model_dump()
    assert d["graph_id"] == d["workflow_id"] == gid


@settings(max_examples=80)
@given(wid=_id)
def test_workflow_id_only_backfills_graph_id(wid):
    """(ii) workflow_id only -> both keys equal on output."""
    d = _build(workflow_id=wid).model_dump()
    assert d["graph_id"] == d["workflow_id"] == wid


@settings(max_examples=80)
@given(ident=_id)
def test_both_present_and_equal_passes(ident):
    """(iii) both equal -> validates and round-trips unchanged."""
    d = _build(graph_id=ident, workflow_id=ident).model_dump()
    assert d["graph_id"] == d["workflow_id"] == ident


@settings(max_examples=80)
@given(gid=_id, wid=_id)
def test_both_present_and_different_raises(gid, wid):
    """(iv) mismatched values raise ValidationError."""
    if gid == wid:
        return  # equality covered above
    with pytest.raises(ValidationError, match="must match"):
        _build(graph_id=gid, workflow_id=wid)


def test_validate_learning_payload_dict_graph_only():
    out = validate_learning_payload("reward.computed", {
        "run_id": "r-1", "workflow_run_id": "wf-1",
        "graph_id": "rt-sast-scan", "idempotency_key": "k",
    })
    assert out["graph_id"] == out["workflow_id"] == "rt-sast-scan"


def test_validate_learning_payload_dict_workflow_only():
    out = validate_learning_payload("reward.computed", {
        "run_id": "r-1", "workflow_run_id": "wf-1",
        "workflow_id": "rt-sast-scan", "idempotency_key": "k",
    })
    assert out["graph_id"] == out["workflow_id"] == "rt-sast-scan"


def test_validate_learning_payload_dict_rejects_mismatch():
    with pytest.raises(ValidationError):
        validate_learning_payload("reward.computed", {
            "run_id": "r-1", "workflow_run_id": "wf-1",
            "graph_id": "rt-sast-scan", "workflow_id": "rt-other",
            "idempotency_key": "k",
        })


# -- Consumer triples -------------------------------------------------------

_TRIPLES = [
    ({"graph_id": "rt-x"}, "rt-x"),
    ({"workflow_id": "rt-x"}, "rt-x"),
    ({"graph_id": "rt-x", "workflow_id": "rt-x"}, "rt-x"),
]


def _capture(handler, event, extras=None):
    extras = extras or {}
    pub: list[tuple[str, dict]] = []
    set_service("tool_invoker_for_caller",
                lambda caller: lambda target, **call: fake("events_publish", **call["arguments"]))

    def fake(tool, **kw):
        if tool == "events_query_events":
            return {"events": [], "total": 0}
        if tool == "events_publish":
            pub.append((kw["event_type"], kw["payload"]))
            return {"event_id": f"evt-{len(pub)}"}
        if tool == "blockchain_get_wallet": return ToolResult(data=GetWalletOutput(wallet_id=kw["wallet_id"], owner_id="agent", balance=0, created_at=""))
        if tool == "blockchain_mint": return ToolResult(data=TransactionOutput(tx_id="tx-1", tx_type="mint", to_wallet=kw["to_wallet"], amount=5, memo="", status="committed"))
        return extras.get(tool, {"ok": True})

    handler(event, fake)
    return pub


@pytest.mark.parametrize("id_keys,expected", _TRIPLES)
def test_rewards_handler_dual_emits(monkeypatch, id_keys, expected):
    monkeypatch.setattr(
        "factory.events.runtime.rewards_handler._run_rl_loop",
        lambda *a, **kw: {"source_id": "gt-findings",
                          "scoring": {"f1": 0.5},
                          "blockchain": {"amount": 50.0, "wallet_id": "w"}},
    )
    event = Event(source="agent.graph", type="graph.completed",
                  payload={"run_id": "r", "execution_time": 1.0, **id_keys})
    pub = _capture(handle_rewards_process, event)
    assert pub[0][1]["graph_id"] == pub[0][1]["workflow_id"] == expected


@pytest.mark.parametrize("id_keys,expected", _TRIPLES)
def test_blockchain_reward_dual_emits(id_keys, expected):
    event = Event(source="events.rewards", type="reward.computed",
                  payload={"run_id": "r", "workflow_run_id": "wf",
                           "reward_value": 5, "reward_unit": "tokens",
                           **id_keys})
    pub = _capture(handle_blockchain_reward, event,
                   extras={"blockchain_mint": {"tx_id": "tx-1", "to_wallet": "w"}})
    assert pub[0][1]["graph_id"] == pub[0][1]["workflow_id"] == expected


@pytest.mark.parametrize("id_keys,expected", _TRIPLES)
def test_memory_learning_dual_emits(id_keys, expected):
    event = Event(source="events.rewards", type="reward.computed",
                  payload={"run_id": "r", "workflow_run_id": "wf",
                           "score": 0.5, "vuln_class": "IDOR",
                           "target_app": "App", "workflow_type": "dast",
                           **id_keys})
    pub = _capture(handle_memory_learning, event,
                   extras={"memory_memory_store": _stored_memory()})
    assert pub[0][1]["graph_id"] == pub[0][1]["workflow_id"] == expected


@pytest.mark.parametrize("id_keys,expected", _TRIPLES)
def test_convergence_dual_emits_and_labels_workflow(id_keys, expected):
    state: dict = {}

    def fake(tool, **kw):
        if tool == "events_query_events":
            return {"events": [], "total": 0}
        if tool == "metrics_record":
            state["label"] = kw["labels"]["workflow"]
            return ok(RecordOutput(
                ok=True, metric_id=kw["metric_id"], value=0.0, timestamp=1.0))
        if tool == "metrics_detect_drift":
            return ok(DriftOutput(metric_id="pipeline-f1", drifted=False))
        if tool == "events_publish":
            state["pub"] = kw["payload"]
            return {"event_id": "evt-1"}
        return {"ok": True}

    event = Event(source="events.rewards", type="reward.computed",
                  payload={"run_id": "r", "workflow_run_id": "wf",
                           "score": 0.5, **id_keys})
    handle_convergence_check(event, fake)
    assert state["label"] == expected
    assert state["pub"]["graph_id"] == state["pub"]["workflow_id"] == expected
