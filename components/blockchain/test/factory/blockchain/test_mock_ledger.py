"""Tests for the MockLedger — wallet, transfer, bounty, chain operations."""

import pytest

from factory.blockchain.runtime.ledger.mock_ledger import MockLedger
from factory.blockchain.runtime.models import (
    BountyStatus, TransactionStatus, TransactionType,
)


@pytest.fixture
def ledger():
    return MockLedger(total_supply=10_000.0)


def test_genesis_creates_treasury(ledger):
    info = ledger.get_chain_info()
    assert info.height == 1  # genesis block
    assert info.total_supply == 10_000.0
    assert info.wallet_count == 1
    treasury = ledger.get_wallet("wallet-treasury")
    assert treasury is not None
    assert treasury.balance == 10_000.0


def test_create_wallet(ledger):
    w = ledger.create_wallet("agent-001", initial_balance=100)
    assert w.wallet_id == "wallet-agent-001"
    assert w.balance == 100.0
    assert ledger.get_balance("wallet-treasury") == 9_900.0


def test_create_wallet_duplicate_raises(ledger):
    ledger.create_wallet("agent-001")
    with pytest.raises(ValueError, match="already exists"):
        ledger.create_wallet("agent-001")


def test_transfer(ledger):
    ledger.create_wallet("alice", initial_balance=500)
    ledger.create_wallet("bob", initial_balance=0)
    tx = ledger.transfer("wallet-alice", "wallet-bob", 200, "payment")
    assert tx.status == TransactionStatus.COMMITTED
    assert tx.tx_type == TransactionType.TRANSFER
    assert tx.amount == 200.0
    assert ledger.get_balance("wallet-alice") == 300.0
    assert ledger.get_balance("wallet-bob") == 200.0


def test_transfer_insufficient_balance(ledger):
    ledger.create_wallet("poor", initial_balance=10)
    ledger.create_wallet("rich")
    with pytest.raises(ValueError, match="Invalid transfer"):
        ledger.transfer("wallet-poor", "wallet-rich", 100)


def test_transfer_negative_amount(ledger):
    ledger.create_wallet("a1", initial_balance=100)
    ledger.create_wallet("a2")
    with pytest.raises(ValueError, match="Invalid transfer"):
        ledger.transfer("wallet-a1", "wallet-a2", -10)


def test_mint(ledger):
    ledger.create_wallet("minter")
    tx = ledger.mint("wallet-minter", 500, "bonus")
    assert tx.tx_type == TransactionType.MINT
    assert ledger.get_balance("wallet-minter") == 500.0


def test_post_and_claim_bounty(ledger):
    ledger.create_wallet("poster", initial_balance=1000)
    ledger.create_wallet("claimer")
    bounty = ledger.post_bounty("wallet-poster", 300, "fix bug", {"type": "code"})
    assert bounty.status == BountyStatus.OPEN
    assert bounty.amount == 300.0
    assert ledger.get_balance("wallet-poster") == 700.0
    tx = ledger.claim_bounty(bounty.bounty_id, "wallet-claimer")
    assert tx.tx_type == TransactionType.BOUNTY_RELEASE
    assert ledger.get_balance("wallet-claimer") == 300.0
    updated = ledger.get_bounty(bounty.bounty_id)
    assert updated.status == BountyStatus.CLAIMED


def test_claim_already_claimed_bounty(ledger):
    ledger.create_wallet("p", initial_balance=500)
    ledger.create_wallet("c1")
    ledger.create_wallet("c2")
    b = ledger.post_bounty("wallet-p", 100)
    ledger.claim_bounty(b.bounty_id, "wallet-c1")
    with pytest.raises(ValueError, match="not open"):
        ledger.claim_bounty(b.bounty_id, "wallet-c2")


def test_cancel_bounty(ledger):
    ledger.create_wallet("cp", initial_balance=500)
    b = ledger.post_bounty("wallet-cp", 200, "cancel me")
    assert ledger.get_balance("wallet-cp") == 300.0
    ledger.cancel_bounty(b.bounty_id)
    assert ledger.get_balance("wallet-cp") == 500.0
    assert ledger.get_bounty(b.bounty_id).status == BountyStatus.CANCELLED


def test_cancel_claimed_bounty_raises(ledger):
    ledger.create_wallet("cp2", initial_balance=500)
    ledger.create_wallet("cl2")
    b = ledger.post_bounty("wallet-cp2", 100)
    ledger.claim_bounty(b.bounty_id, "wallet-cl2")
    with pytest.raises(ValueError, match="Cannot cancel"):
        ledger.cancel_bounty(b.bounty_id)


def test_list_bounties_filter(ledger):
    ledger.create_wallet("bp", initial_balance=1000)
    ledger.create_wallet("bc")
    ledger.post_bounty("wallet-bp", 100, "b1")
    b2 = ledger.post_bounty("wallet-bp", 200, "b2")
    ledger.claim_bounty(b2.bounty_id, "wallet-bc")
    assert len(ledger.list_bounties(status="open")) == 1
    assert len(ledger.list_bounties(status="claimed")) == 1
    assert len(ledger.list_bounties()) == 2


def test_get_transactions(ledger):
    ledger.create_wallet("tx1", initial_balance=500)
    ledger.create_wallet("tx2")
    ledger.transfer("wallet-tx1", "wallet-tx2", 100)
    txs = ledger.get_transactions("wallet-tx1")
    assert any(t.from_wallet == "wallet-tx1" for t in txs)


def test_chain_integrity(ledger):
    ledger.create_wallet("v1", initial_balance=100)
    ledger.transfer("wallet-v1", "wallet-treasury", 50)
    result = ledger.verify_chain()
    assert result["valid"] is True
    assert result["blocks_checked"] >= 3


def test_reconcile(ledger):
    ledger.create_wallet("rec", initial_balance=500)
    result = ledger.reconcile("wallet-rec")
    assert result["drift"] < 0.01


def test_get_block(ledger):
    block = ledger.get_block(0)
    assert block is not None
    assert block.height == 0
    assert ledger.get_block(9999) is None


def test_health_check(ledger):
    h = ledger.health_check()
    assert h["healthy"] is True
    assert h["provider"] == "mock_ledger"
