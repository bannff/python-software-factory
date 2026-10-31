"""Property tests for MockLedger arithmetic and chain invariants."""
import string

import pytest
from hypothesis import given, settings, strategies as st

from factory.blockchain.runtime.ledger import mock_ledger

MockLedger = mock_ledger.MockLedger
SUPPLY = 10_000.0
owners = st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=10).filter(
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


def test_reserved_treasury_owner_is_rejected_without_side_effects():
    """Treasury genesis is the sole owner of the reserved wallet ID."""
    ledger = MockLedger(total_supply=SUPPLY)
    before = ledger.get_chain_info()
    with pytest.raises(ValueError, match="Wallet already exists: wallet-treasury"):
        ledger.create_wallet("treasury", initial_balance=100)
    assert ledger.get_balance("wallet-treasury") == SUPPLY
    assert ledger.get_chain_info() == before
    assert len(ledger.get_transactions()) == 1


@given(owner=owners, bal=amts)
@settings(max_examples=50, deadline=None)
def test_create_wallet_deducts_from_treasury(owner, bal):
    ledger = MockLedger(total_supply=SUPPLY)
    ledger.create_wallet(owner, initial_balance=bal)
    assert ledger.get_balance(f"wallet-{owner}") == bal
    assert abs(ledger.get_balance("wallet-treasury") - (SUPPLY - bal)) < 1e-9


@given(owner=owners, bal=amts)
@settings(max_examples=50)
def test_transfer_conserves_tokens(owner, bal):
    ledger = MockLedger(total_supply=SUPPLY)
    ledger.create_wallet(owner, initial_balance=bal)
    half = round(bal / 2, 8)
    if half <= 0:
        return
    before_sender = ledger.get_balance(f"wallet-{owner}")
    before_receiver = ledger.get_balance("wallet-treasury")
    ledger.transfer(f"wallet-{owner}", "wallet-treasury", half)
    assert abs(ledger.get_balance(f"wallet-{owner}") - (before_sender - half)) < 1e-9
    assert abs(ledger.get_balance("wallet-treasury") - (before_receiver + half)) < 1e-9


@given(owner=owners, bal=amts, over=amts)
@settings(max_examples=50)
def test_transfer_insufficient_raises(owner, bal, over):
    ledger = MockLedger(total_supply=SUPPLY)
    ledger.create_wallet(owner, initial_balance=bal)
    if over > bal:
        with pytest.raises(ValueError):
            ledger.transfer(f"wallet-{owner}", "wallet-treasury", over)


@given(owner=owners)
@settings(max_examples=50)
def test_duplicate_wallet_raises(owner):
    ledger = MockLedger(total_supply=SUPPLY)
    ledger.create_wallet(owner)
    with pytest.raises(ValueError):
        ledger.create_wallet(owner)


@given(owner=owners, bal=amts, desc=descs)
@settings(max_examples=50)
def test_bounty_escrow_deducts_from_poster(owner, bal, desc):
    ledger = MockLedger(total_supply=SUPPLY)
    ledger.create_wallet(owner, initial_balance=bal)
    half = round(bal / 2, 8)
    if half <= 0:
        return
    before = ledger.get_balance(f"wallet-{owner}")
    bounty = ledger.post_bounty(f"wallet-{owner}", half, desc)
    assert abs(ledger.get_balance(f"wallet-{owner}") - (before - half)) < 1e-9
    assert bounty.amount == half


@given(owner=owners, claimer=owners, bal=amts)
@settings(max_examples=50)
def test_claim_credits_claimer(owner, claimer, bal):
    if owner == claimer:
        return
    ledger = MockLedger(total_supply=SUPPLY)
    ledger.create_wallet(owner, initial_balance=bal)
    ledger.create_wallet(claimer, initial_balance=0)
    half = round(bal / 2, 8)
    if half > 0:
        bounty = ledger.post_bounty(f"wallet-{owner}", half)
        ledger.claim_bounty(bounty.bounty_id, f"wallet-{claimer}")
        assert abs(ledger.get_balance(f"wallet-{claimer}") - half) < 1e-9


@given(owner=owners, c1=owners, c2=owners, bal=amts)
@settings(max_examples=50)
def test_double_claim_raises(owner, c1, c2, bal):
    if len({owner, c1, c2}) < 3:
        return
    ledger = MockLedger(total_supply=SUPPLY)
    ledger.create_wallet(owner, initial_balance=bal)
    ledger.create_wallet(c1)
    ledger.create_wallet(c2)
    half = round(bal / 2, 8)
    if half > 0:
        bounty = ledger.post_bounty(f"wallet-{owner}", half)
        ledger.claim_bounty(bounty.bounty_id, f"wallet-{c1}")
        with pytest.raises(ValueError):
            ledger.claim_bounty(bounty.bounty_id, f"wallet-{c2}")


@given(owner=owners, bal=amts)
@settings(max_examples=50)
def test_chain_valid_after_operations(owner, bal):
    ledger = MockLedger(total_supply=SUPPLY)
    ledger.create_wallet(owner, initial_balance=bal)
    half = round(bal / 2, 8)
    if half > 0:
        ledger.transfer(f"wallet-{owner}", "wallet-treasury", half)
    assert ledger.verify_chain()["valid"]
