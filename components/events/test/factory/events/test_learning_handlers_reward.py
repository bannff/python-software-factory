"""Reward-handler ToolResult ledger-envelope regressions."""
from factory.blockchain.mcp.contracts.deterministic import GetWalletOutput
from factory.blockchain.mcp.contracts.ledger import TransactionOutput
from factory.blockchain.mcp.contracts.operational import CreateWalletOutput
from factory.events.runtime.learning_handlers import handle_blockchain_reward
from factory.events.runtime.models import Event
from factory.mcp_utils.interface import ToolResult


def _event(value: float) -> Event:
    return Event(source="events.rewards", type="reward.computed", payload={"run_id": "run-j5me", "workflow_run_id": "wf-j5me", "reward_value": value, "reward_unit": "tokens", "score": 0.6667, "vuln_class": "IDOR", "principal_id": "kiro-agent"}, principal_id="kiro-agent")


def test_reward_handler_creates_missing_wallet_then_mints() -> None:
    calls, published = [], []
    missing = GetWalletOutput(wallet_id="wallet-kiro-agent", owner_id="", balance=0, created_at="", found=False, error="not_found")
    created = CreateWalletOutput(wallet_id="wallet-kiro-agent", owner_id="kiro-agent", balance=0, created_at="")
    minted = TransactionOutput(tx_id="tx-bd-j5me", tx_type="mint", to_wallet="wallet-kiro-agent", amount=66.67, memo="", status="committed")

    def invoke(name, **kwargs):
        calls.append((name, kwargs))
        if name == "events_query_events": return {"events": [], "total": 0}
        if name == "blockchain_get_wallet": return ToolResult(data=missing)
        if name == "blockchain_create_wallet": return ToolResult(data=created)
        if name == "blockchain_mint": return ToolResult(data=minted)
        if name == "events_publish": published.append(kwargs); return {"event_id": "evt"}
        raise AssertionError(name)

    result = handle_blockchain_reward(_event(66.67), invoke)
    names = [name for name, _ in calls]
    assert names.index("blockchain_get_wallet") < names.index("blockchain_create_wallet") < names.index("blockchain_mint")
    assert result["transaction_id"] == "tx-bd-j5me"
    assert published[0]["payload"]["wallet_id"] == "wallet-kiro-agent"


def test_reward_handler_skips_create_for_existing_wallet() -> None:
    calls = []
    existing = GetWalletOutput(wallet_id="wallet-kiro-agent", owner_id="kiro-agent", balance=100, created_at="")
    minted = TransactionOutput(tx_id="tx-existing", tx_type="mint", to_wallet="wallet-kiro-agent", amount=5, memo="", status="committed")

    def invoke(name, **kwargs):
        calls.append(name)
        if name == "events_query_events": return {"events": [], "total": 0}
        if name == "blockchain_get_wallet": return ToolResult(data=existing)
        if name == "blockchain_create_wallet": raise AssertionError("must not create")
        if name == "blockchain_mint": return ToolResult(data=minted)
        if name == "events_publish": return {"event_id": "evt"}
        raise AssertionError(name)

    result = handle_blockchain_reward(_event(5), invoke)
    assert "blockchain_create_wallet" not in calls
    assert calls.index("blockchain_get_wallet") < calls.index("blockchain_mint")
    assert result["transaction_id"] == "tx-existing"
