"""Graph entities must store enum values, not 'TransactionStatus.COMMITTED' (#381)."""
from __future__ import annotations

from factory.blockchain.runtime import graph_sync
from factory.blockchain.runtime.models import Bounty, BountyStatus, Transaction, TransactionStatus, TransactionType


def _capture(monkeypatch) -> list[dict]:
    calls: list[dict] = []
    monkeypatch.setattr(graph_sync, "_invoke", lambda _tool, **kw: calls.append(kw))
    return calls


def test_transaction_props_carry_plain_values(monkeypatch) -> None:
    calls = _capture(monkeypatch)
    graph_sync.sync_transaction(Transaction(
        tx_id="t", tx_type=TransactionType.MINT, to_wallet="w", amount=1.0,
        status=TransactionStatus.COMMITTED,
    ))
    props = calls[0]["properties"]
    assert props["status"] == "committed" and props["tx_type"] == "mint"


def test_bounty_props_carry_plain_values(monkeypatch) -> None:
    calls = _capture(monkeypatch)
    graph_sync.sync_bounty(Bounty(bounty_id="b", poster_wallet="w", amount=1.0, status=BountyStatus.OPEN))
    assert calls[0]["properties"]["status"] == "open"
