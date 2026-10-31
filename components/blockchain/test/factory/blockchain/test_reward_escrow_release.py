"""S4b guard tests: eval-gated reward escrow/release ledger truth."""
from factory.blockchain.runtime.ledger.mock_ledger import MockLedger


def _escrowed(ledger: MockLedger, run_id: str = "run-abc") -> dict:
    return ledger.escrow_reward(
        run_id=run_id, to_wallet="wallet-agent", amount=25.0, memo="RL:IDOR",
    )


def test_escrow_parks_funds_without_crediting_wallet() -> None:
    ledger = MockLedger()
    ledger.create_wallet("agent")
    record = _escrowed(ledger)
    assert record["status"] == "escrowed"
    assert ledger.get_balance("wallet-agent") == 0.0
    assert ledger.get_reward_escrow("run-abc")["escrow_tx_id"] == record["escrow_tx_id"]


def test_release_credits_wallet_exactly_once() -> None:
    """Duplicate release event produces exactly one wallet movement."""
    ledger = MockLedger()
    ledger.create_wallet("agent")
    _escrowed(ledger)
    assert ledger.get_balance("wallet-agent") == 0.0

    first = ledger.release_reward("run-abc")
    assert first["status"] == "released"
    assert ledger.get_balance("wallet-agent") == 25.0

    second = ledger.release_reward("run-abc")
    assert second.get("already_released") is True
    assert ledger.get_balance("wallet-agent") == 25.0

    # One BOUNTY_RELEASE tx against the agent wallet, ledger truth intact.
    moves = [
        tx for tx in ledger.get_transactions()
        if tx.to_wallet == "wallet-agent" and tx.from_wallet is None
    ]
    assert [tx.tx_type.value for tx in moves] == ["bounty_release"]


def test_release_without_escrow_is_loud() -> None:
    ledger = MockLedger()
    try:
        ledger.release_reward("run-missing")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "No pending reward escrow" in str(exc)


def test_escrow_is_idempotent_per_run_never_double_escrows() -> None:
    ledger = MockLedger()
    ledger.create_wallet("agent")
    first = _escrowed(ledger)
    second = _escrowed(ledger)
    assert first["escrow_tx_id"] == second["escrow_tx_id"]
    assert first["amount"] != "" and first["amount"] == second["amount"]


def test_released_escrow_is_terminal_for_redelivered_reward() -> None:
    """Redelivered reward.computed after release must NOT re-escrow: the
    released record is terminal and the wallet keeps exactly one movement."""
    ledger = MockLedger()
    ledger.create_wallet("agent")
    ledger.escrow_reward("run-abc", "wallet-agent", 25.0, "RL:IDOR")
    ledger.release_reward("run-abc")
    again = ledger.escrow_reward("run-abc", "wallet-agent", 25.0, "RL:IDOR")
    assert again["status"] == "released"
    assert ledger.get_balance("wallet-agent") == 25.0
    assert ledger.release_reward("run-abc").get("already_released") is True
    assert ledger.get_balance("wallet-agent") == 25.0
