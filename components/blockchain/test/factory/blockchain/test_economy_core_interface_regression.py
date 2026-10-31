"""Regression coverage for the legacy economy core convenience interface."""
from __future__ import annotations

from factory.blockchain import core
from factory.blockchain.runtime.ledger import mock_ledger


def test_core_facade_keeps_single_runtime_and_legacy_economy_operations(monkeypatch) -> None:
    no_op = lambda *_args, **_kwargs: None
    for name in ("sync_block", "sync_bounty", "sync_transaction", "sync_wallet"):
        monkeypatch.setattr(mock_ledger, name, no_op)
    monkeypatch.setattr(mock_ledger.event_emitter, "emit", no_op)
    core.reset_runtime()
    try:
        first = core.get_runtime()
        assert first is core.get_runtime()
        wallet = core.create_wallet("core-regression", initial_balance=7)
        transfer = core.transfer(wallet["wallet_id"], "wallet-treasury", 2, "legacy")
        assert core.get_balance(wallet["wallet_id"]) == 5
        assert transfer["tx_type"] == "transfer"
        assert core.health_check()["provider"] == "mock_ledger"
    finally:
        core.reset_runtime()
