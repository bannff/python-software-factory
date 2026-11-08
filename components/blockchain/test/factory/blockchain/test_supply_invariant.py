"""total_supply must equal the sum of wallet balances after every operation (#380)."""
from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from factory.blockchain.runtime.errors import LedgerError
from factory.blockchain.runtime.ledger import mock_ledger
from factory.blockchain.runtime.ledger.mock_ledger import MockLedger



@pytest.fixture(autouse=True)
def isolate_side_effects(monkeypatch):
    no_op = lambda *_a, **_k: None
    for name in ("sync_block", "sync_bounty", "sync_transaction", "sync_wallet"):
        monkeypatch.setattr(mock_ledger, name, no_op)
    monkeypatch.setattr(mock_ledger.event_emitter, "emit", no_op)


_OWNERS = ("a", "b", "c")
_op = st.tuples(
    st.sampled_from(("mint", "transfer", "post", "claim", "cancel", "reward")),
    st.sampled_from(_OWNERS), st.sampled_from(_OWNERS),
    st.floats(min_value=0.5, max_value=500, allow_nan=False),
)


def _supply_gap(ledger: MockLedger) -> float:
    held = sum(w.balance for w in ledger.list_wallets(limit=1000))
    escrowed = sum(b.amount for b in ledger.list_bounties(status="open", limit=1000))
    return ledger.get_chain_info().total_supply - held - escrowed


def test_mint_grows_supply() -> None:
    ledger = MockLedger(total_supply=1000.0)
    ledger.create_wallet("a")
    ledger.mint("wallet-a", 50.0)
    assert ledger.get_chain_info().total_supply == 1050.0


def test_reward_release_grows_supply() -> None:
    ledger = MockLedger(total_supply=1000.0)
    ledger.create_wallet("a")
    ledger.escrow_reward("run-1", "wallet-a", 11.0)
    assert ledger.get_chain_info().total_supply == 1000.0  # parked, not yet minted
    ledger.release_reward("run-1")
    ledger.release_reward("run-1")  # replay must not mint twice
    assert ledger.get_chain_info().total_supply == 1011.0


@settings(max_examples=60, deadline=None)
@given(st.lists(_op, max_size=25))
def test_supply_equals_wallets_plus_open_bounties(ops) -> None:
    ledger = MockLedger(total_supply=10_000.0)
    for owner in _OWNERS:
        ledger.create_wallet(owner)
    for i, (kind, x, y, amount) in enumerate(ops):
        try:
            if kind == "mint":
                ledger.mint(f"wallet-{x}", amount)
            elif kind == "transfer":
                ledger.transfer(f"wallet-{x}", f"wallet-{y}", amount)
            elif kind == "post":
                ledger.post_bounty(f"wallet-{x}", amount)
            elif kind == "claim":
                open_ = ledger.list_bounties(status="open", limit=1)
                if open_:
                    ledger.claim_bounty(open_[0].bounty_id, f"wallet-{y}")
            elif kind == "cancel":
                open_ = ledger.list_bounties(status="open", limit=1)
                if open_:
                    ledger.cancel_bounty(open_[0].bounty_id)
            else:
                ledger.escrow_reward(f"run-{i}", f"wallet-{x}", amount)
                ledger.release_reward(f"run-{i}")
        except (LedgerError, ValueError):
            pass
        assert _supply_gap(ledger) == pytest.approx(0.0, abs=1e-6)


def test_neo4j_mint_and_release_grow_supply(monkeypatch) -> None:
    from types import SimpleNamespace

    from factory.blockchain.runtime.ledger.neo4j_bounty import Neo4jBountyMixin
    from factory.blockchain.runtime.ledger.neo4j_ledger import Neo4jLedger

    class Fake(Neo4jBountyMixin, Neo4jLedger):
        def __init__(self) -> None:
            self._total_supply = 100.0
            self.escrow = {"wallet_id": "w", "amount": 7.0, "escrow_tx_id": "e", "memo": "m"}

        def _get_wallet_props(self, _wid):
            return {"balance": 0.0}

        def _update_wallet_balance(self, *_a):
            pass

        def _make_tx(self, *_a):
            return SimpleNamespace(tx_id="t")

        def _commit_block(self, *_a):
            pass

        def get_reward_escrow(self, _run_id):
            return self.escrow

    ledger = Fake()
    ledger.mint("w", 5.0)
    assert ledger._total_supply == 105.0
    from factory.blockchain.runtime.ledger import neo4j_rewards
    monkeypatch.setattr(neo4j_rewards, "_add_entity", lambda *_a, **_k: None)
    ledger.release_reward("run")
    assert ledger._total_supply == 112.0
