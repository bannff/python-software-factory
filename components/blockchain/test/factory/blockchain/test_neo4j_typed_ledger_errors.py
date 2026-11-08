"""Neo4j ledger refusals carry the same stable codes as the mock ledger (issue #375).

Refusals all happen before any write, so a seam-stubbed ledger exercises them
without a server.
"""
from __future__ import annotations

import pytest

from factory.blockchain.runtime.errors import LedgerError
from factory.blockchain.runtime.ledger.neo4j_bounty import Neo4jBountyMixin
from factory.blockchain.runtime.ledger.neo4j_ledger import Neo4jLedger


class FakeLedger(Neo4jBountyMixin, Neo4jLedger):
    def __init__(self, wallets: dict, bounties: dict | None = None) -> None:
        self.wallets, self.bounties = wallets, bounties or {}

    def _get_wallet_props(self, wid):
        return self.wallets.get(wid)

    def _get_bounty_props(self, bid):
        return self.bounties.get(bid)


def _code(call) -> str:
    with pytest.raises(LedgerError) as caught:
        call()
    return caught.value.code


@pytest.fixture
def ledger() -> FakeLedger:
    return FakeLedger(
        {"a": {"balance": 5.0}, "b": {"balance": 0.0}},
        {"open": {"status": "open", "amount": 1}, "done": {"status": "claimed", "amount": 1}},
    )


def test_transfer_codes(ledger) -> None:
    assert _code(lambda: ledger.transfer("nobody", "b", 1)) == "wallet_not_found"
    assert _code(lambda: ledger.transfer("a", "nobody", 1)) == "wallet_not_found"
    assert _code(lambda: ledger.transfer("a", "b", -1)) == "invalid_amount"
    assert _code(lambda: ledger.transfer("a", "b", 50)) == "insufficient_balance"


def test_mint_codes(ledger) -> None:
    assert _code(lambda: ledger.mint("nobody", 1)) == "wallet_not_found"
    assert _code(lambda: ledger.mint("a", 0)) == "invalid_amount"


def test_post_bounty_codes(ledger) -> None:
    assert _code(lambda: ledger.post_bounty("nobody", 1)) == "wallet_not_found"
    assert _code(lambda: ledger.post_bounty("a", 0)) == "invalid_amount"
    assert _code(lambda: ledger.post_bounty("a", 99999)) == "insufficient_balance"


def test_claim_bounty_codes(ledger) -> None:
    assert _code(lambda: ledger.claim_bounty("missing", "b")) == "bounty_not_found"
    assert _code(lambda: ledger.claim_bounty("done", "b")) == "bounty_not_open"
    assert _code(lambda: ledger.claim_bounty("open", "nobody")) == "wallet_not_found"
