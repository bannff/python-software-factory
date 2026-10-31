"""Stateful property tests for MockLedger arithmetic and chain invariants."""

import pytest
from hypothesis import settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from factory.blockchain.runtime.ledger import mock_ledger

MockLedger = mock_ledger.MockLedger

SUPPLY = 10_000.0
owners = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10).filter(
    lambda owner: owner != "treasury",
)
amts = st.floats(min_value=0.01, max_value=1000.0, allow_nan=False, allow_infinity=False)
descs = st.text(min_size=0, max_size=50)


@pytest.fixture(autouse=True)
def isolate_mock_ledger_side_effects(monkeypatch):
    """Keep ledger properties independent of graph and event integrations."""
    no_op = lambda *_args, **_kwargs: None
    for name in ("sync_block", "sync_bounty", "sync_transaction", "sync_wallet"):
        monkeypatch.setattr(mock_ledger, name, no_op)
    monkeypatch.setattr(mock_ledger.event_emitter, "emit", no_op)


class LedgerMachine(RuleBasedStateMachine):
    """Random wallet/transfer/bounty ops with conservation checks."""

    def __init__(self):
        super().__init__()
        self.ledger = None
        self.wallets: set[str] = set()
        self.open_escrows = 0.0

    @initialize()
    def start(self):
        self.ledger = MockLedger(total_supply=SUPPLY)
        self.wallets = {"wallet-treasury"}
        self.open_escrows = 0.0

    @rule(owner=owners, bal=amts)
    def create_wallet(self, owner, bal):
        wallet_id = f"wallet-{owner}"
        if wallet_id in self.wallets or bal > self.ledger.get_balance("wallet-treasury"):
            return
        self.ledger.create_wallet(owner, initial_balance=bal)
        self.wallets.add(wallet_id)

    @rule(amt=amts)
    def transfer_to_treasury(self, amt):
        wallets = [wallet for wallet in self.wallets if wallet != "wallet-treasury"]
        if not wallets or self.ledger.get_balance(wallets[0]) < amt:
            return
        self.ledger.transfer(wallets[0], "wallet-treasury", amt)

    @rule(amt=amts, desc=descs)
    def post_bounty(self, amt, desc):
        wallets = [wallet for wallet in self.wallets if wallet != "wallet-treasury"]
        if not wallets or self.ledger.get_balance(wallets[0]) < amt:
            return
        self.ledger.post_bounty(wallets[0], amt, desc)
        self.open_escrows += amt

    @rule()
    def claim_open_bounty(self):
        open_bounties = self.ledger.list_bounties(status="open")
        if not open_bounties:
            return
        candidates = [wallet for wallet in self.wallets if wallet != open_bounties[0].poster_wallet]
        if not candidates:
            return
        self.ledger.claim_bounty(open_bounties[0].bounty_id, candidates[0])
        self.open_escrows -= open_bounties[0].amount

    @invariant()
    def chain_valid(self):
        assert self.ledger is None or self.ledger.verify_chain()["valid"]

    @invariant()
    def balances_non_negative(self):
        if self.ledger is not None:
            assert all(self.ledger.get_balance(wallet) >= 0 for wallet in self.wallets)

    @invariant()
    def token_conservation(self):
        if self.ledger is not None:
            balance = sum(self.ledger.get_balance(wallet) for wallet in self.wallets)
            assert abs(balance + self.open_escrows - SUPPLY) < 1e-6


TestLedgerStateful = LedgerMachine.TestCase
TestLedgerStateful.settings = settings(max_examples=50, stateful_step_count=30)
