"""S4b guard: escrow-on-publish → release-on-eval → wallet credit happy path.

Non-GT reward.computed never touches blockchain_mint; the credit lands only
when the eval projection commits durable evidence for the run.
"""
from factory.blockchain.mcp.contracts.deterministic import GetWalletOutput
from factory.blockchain.mcp.contracts.ledger import TransactionOutput
from factory.blockchain.mcp.contracts.operational import CreateWalletOutput
from factory.blockchain.runtime.ledger.mock_ledger import MockLedger
from factory.events.runtime._dispatch_evals import _persist_eval_result
from factory.events.runtime.learning_handlers import handle_blockchain_reward
from factory.events.runtime.models import Event
from factory.mcp_utils.interface import ToolResult


def _reward_event(run_id: str) -> Event:
    return Event(
        source="events.rewards", type="reward.computed",
        payload={
            "run_id": run_id, "workflow_run_id": run_id,
            "reward_value": 25.0, "reward_unit": "tokens", "score": 0.4,
            "source_id": "events.rewards",  # non-GT: payout must be eval-gated
            "principal_id": "kiro-agent",
        },
        principal_id="kiro-agent",
    )


def test_non_gt_reward_escrows_never_mints() -> None:
    calls, published = [], []

    def invoke(name, **kwargs):
        calls.append(name)
        if name == "events_query_events":
            return {"events": [], "total": 0}
        if name == "blockchain_get_wallet":
            return ToolResult(data=GetWalletOutput(
                wallet_id="wallet-kiro-agent", owner_id="kiro-agent", balance=0, created_at=""))
        if name == "blockchain_mint":
            raise AssertionError("NON-GT reward must not mint immediately")
        if name == "blockchain_reward_escrow":
            return ToolResult(data=TransactionOutput(
                tx_id="tx-escrow-1", tx_type="bounty_escrow", amount=25.0, status="escrowed"))
        if name == "events_publish":
            published.append(kwargs)
            return {"event_id": "evt"}
        raise AssertionError(name)

    result = handle_blockchain_reward(_reward_event("run-e9"), invoke)
    assert result["status"] == "escrowed" and result["escrowed"] is True
    assert calls.count("blockchain_reward_escrow") == 1
    assert published == [], "wallet.rewarded only fires on the release leg"


def test_non_gt_escrow_provisions_missing_wallet_like_gt_leg() -> None:
    """A not-yet-created wallet must be provisioned before escrow — otherwise
    the payout drops silently and every redelivery keeps failing."""
    calls = []

    def invoke(name, **kwargs):
        calls.append(name)
        if name == "events_query_events":
            return {"events": [], "total": 0}
        if name == "blockchain_get_wallet":
            return ToolResult(data=GetWalletOutput(
                wallet_id="wallet-kiro-agent", owner_id="", balance=0,
                created_at="", found=False, error="not_found"))
        if name == "blockchain_create_wallet":
            return ToolResult(data=CreateWalletOutput(
                wallet_id="wallet-kiro-agent", owner_id="kiro-agent", balance=0, created_at=""))
        if name == "blockchain_reward_escrow":
            return ToolResult(data=TransactionOutput(
                tx_id="tx-escrow-2", tx_type="bounty_escrow", amount=25.0, status="escrowed"))
        raise AssertionError(name)

    result = handle_blockchain_reward(_reward_event("run-e9"), invoke)
    assert result["status"] == "escrowed"
    assert calls.index("blockchain_get_wallet") < calls.index("blockchain_create_wallet") < calls.index("blockchain_reward_escrow")
    assert calls.count("blockchain_reward_escrow") == 1


def _release_invoker(ledger: MockLedger):
    published = []
    wallet_store: list[dict] = []
    released = {}

    def invoke(name, **kwargs):
        if name == "evals_record_run":
            return ToolResult(data={
                "persisted": True, "pointer": {"doc_id": "doc-e9"},
                "projection_key": "eval:doc-e9",
            })
        if name == "blockchain_reward_release":
            run_id = kwargs["run_id"]
            released[run_id] = released.get(run_id, 0) + 1
            tx = ledger.release_reward(run_id)
            return ToolResult(data={
                "tx_id": tx["release_tx_id"], "tx_type": "bounty_release",
                "to_wallet": tx["wallet_id"], "amount": tx["amount"],
                "status": "released", "already_released": released[run_id] > 1,
            })
        if name == "events_query_events":
            matches = [e for e in wallet_store
                       if e.get("idempotency_key") == kwargs.get("payload_value")]
            return {"events": matches, "total": len(matches)}
        if name == "events_publish":
            published.append(kwargs)
            if kwargs["event_type"] == "wallet.rewarded":
                wallet_store.append(kwargs["payload"])
            return {"event_id": "evt"}
        raise AssertionError(name)

    return invoke, published, released


def test_release_on_eval_projection_credits_wallet_once() -> None:
    ledger = MockLedger()
    ledger.create_wallet("kiro-agent")
    run_id = "run-e9"
    ledger.escrow_reward(run_id=run_id, to_wallet="wallet-kiro-agent", amount=25.0)
    invoke, published, released = _release_invoker(ledger)
    record_run = {"run_id": run_id, "workflow_id": "wf-e9",
                  "summary": {"avg_score": 0.4, "pass_rate": 0.0},
                  "results": [{"case_name": "c", "score": 0.4}]}

    _persist_eval_result(invoke, record_run, record_run)
    assert released[run_id] == 1
    assert ledger.get_balance("wallet-kiro-agent") == 25.0
    wallet_events = [p for p in published if p["event_type"] == "wallet.rewarded"]
    assert len(wallet_events) == 1
    assert wallet_events[0]["payload"]["idempotency_key"] == "wallet:run-e9:25.0"
    eval_events = [p for p in published if p["event_type"] == "eval.completed"]
    assert len(eval_events) == 1

    # Duplicate eval projection for the same run: contract requires exactly
    # one wallet movement, no second wallet.rewarded.
    _persist_eval_result(invoke, record_run, record_run)
    assert ledger.get_balance("wallet-kiro-agent") == 25.0
    wallet_events = [p for p in published if p["event_type"] == "wallet.rewarded"]
    assert len(wallet_events) == 1


def test_release_skipped_without_durable_evidence() -> None:
    ledger = MockLedger()
    ledger.create_wallet("kiro-agent")
    run_id = "run-f0"
    ledger.escrow_reward(run_id=run_id, to_wallet="wallet-kiro-agent", amount=25.0)
    invoke, published, _ = _release_invoker(ledger)

    def invoke_no_eval(name, **kwargs):
        if name == "evals_record_run":
            return ToolResult(data={"persisted": False, "reason": "no case results to record"})
        return invoke(name, **kwargs)

    _persist_eval_result(invoke_no_eval, {"run_id": run_id, "results": []}, {"results": []})
    assert ledger.get_balance("wallet-kiro-agent") == 0.0
    assert published == [], "no wallet reward without eval evidence"
