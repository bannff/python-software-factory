"""Blockchain reward and memory-learning handler tests."""
from factory.blockchain.mcp.contracts.deterministic import GetWalletOutput
from factory.blockchain.mcp.contracts.ledger import TransactionOutput
from factory.events.runtime.learning_handlers import handle_blockchain_reward, handle_memory_learning
from factory.events.runtime.models import Event
from factory.memory.mcp.contracts.base import MemoryData
from factory.memory.mcp.contracts.operational import MemoryStoreOutput
from factory.mcp_utils.interface import ToolResult


def _stored_memory() -> ToolResult[MemoryStoreOutput]:
    return ToolResult(data=MemoryStoreOutput(stored=True, memory=MemoryData(
        id="mem-123", user_id="kiro-agent", content="fact", memory_type="long_term",
        category="fact", metadata={}, relevance_score=1.0, created_at="2026-01-01T00:00:00Z")))


def test_blockchain_reward_handler_mints_and_emits_wallet_event() -> None:
    published = []
    wallet = GetWalletOutput(wallet_id="wallet-kiro-agent", owner_id="kiro-agent", balance=0, created_at="")
    mint = TransactionOutput(tx_id="tx-123", tx_type="mint", to_wallet="wallet-kiro-agent", amount=12, memo="", status="committed")

    def invoke(name, **kwargs):
        if name == "events_query_events": return {"events": [], "total": 0}
        if name == "blockchain_get_wallet": return ToolResult(data=wallet)
        if name == "blockchain_mint": return ToolResult(data=mint)
        if name == "events_publish": published.append((kwargs["event_type"], kwargs["payload"])); return {"event_id": "evt-wallet"}
        raise AssertionError(name)

    event = Event(source="events.rewards", type="reward.computed", payload={"run_id": "run-123", "workflow_run_id": "wf-123", "reward_value": 12, "reward_unit": "tokens", "score": 0.82, "vuln_class": "IDOR"})
    result = handle_blockchain_reward(event, invoke)
    assert result["transaction_id"] == "tx-123"
    assert published[0][0] == "wallet.rewarded"
    assert published[0][1]["domain_class"] == "IDOR"


def test_memory_learning_handler_stores_summary_and_emits_event(monkeypatch) -> None:
    published = []
    monkeypatch.setattr(
        "factory.mcp_utils.interface.get_service",
        lambda name: (lambda caller: lambda target, **call: (
            published.append((call["arguments"]["event_type"], call["arguments"]["payload"])),
            {"ok": True},
        )[1]) if name == "tool_invoker_for_caller" else None,
    )

    def invoke(name, **kwargs):
        if name == "events_query_events": return {"events": [], "total": 0}
        if name == "memory_memory_store": return _stored_memory()
        if name == "events_publish": published.append((kwargs["event_type"], kwargs["payload"])); return {"event_id": "evt-memory"}
        raise AssertionError(name)

    event = Event(source="events.rewards", type="reward.computed", payload={"run_id": "run-123", "workflow_run_id": "wf-123", "workflow_type": "dast", "target_app": "WebGoat", "vuln_class": "IDOR", "score": 0.82, "precision": 0.8, "recall": 0.84, "true_positives": 4, "false_positives": 1, "false_negatives": 2})
    assert handle_memory_learning(event, invoke)["memory_id"] == "mem-123"
    assert published[0][0] == "memory.learning_stored"


def test_wallet_reward_handler_skips_duplicate_idempotency_key() -> None:
    def invoke(name, **kwargs):
        if name == "events_query_events": return {"events": [{"id": "evt-existing"}], "total": 1}
        raise AssertionError(name)

    event = Event(source="events.rewards", type="reward.computed", payload={"run_id": "run-123", "workflow_run_id": "wf-123", "reward_value": 12, "profile_version": "v1"})
    assert handle_blockchain_reward(event, invoke)["deduped"] is True
