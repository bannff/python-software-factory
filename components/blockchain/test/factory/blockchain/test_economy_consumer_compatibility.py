"""Consumer compatibility for legacy MockLedger imports and patch seams."""
from __future__ import annotations

from factory.blockchain.runtime.ledger import mock_ledger
from factory.blockchain.runtime.ledger.mock_ledger import MockLedger


def test_mock_ledger_import_and_module_effect_monkeypatch_bindings_remain_live(monkeypatch) -> None:
    observed: list[str] = []
    for name in ("sync_block", "sync_bounty", "sync_transaction", "sync_wallet"):
        monkeypatch.setattr(mock_ledger, name, lambda *_args, _name=name, **_kwargs: observed.append(_name))
    monkeypatch.setattr(mock_ledger.event_emitter, "emit", lambda event, _payload: observed.append(event))
    ledger = MockLedger()
    wallet = ledger.create_wallet("consumer", initial_balance=3)
    ledger.mint(wallet.wallet_id, 1)
    assert isinstance(ledger, mock_ledger.MockLedger)
    assert {"sync_block", "sync_transaction", "sync_wallet", "blockchain.wallet.created", "blockchain.tx.committed"} <= set(observed)


def test_dashboard_public_helpers_keep_empty_optional_service_semantics(monkeypatch) -> None:
    from factory.blockchain.mcp import dashboard_summary

    monkeypatch.setattr(dashboard_summary, "_get_invoker", lambda: None)
    assert dashboard_summary.list_recent_activity() == []
    assert dashboard_summary.list_related_graph_entities(entity_id="tx-missing") == []
