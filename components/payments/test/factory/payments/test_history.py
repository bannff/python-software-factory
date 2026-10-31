"""Tests for payment history - Models.

See also:
- test_history_store.py - InMemoryHistoryStore tests
"""

import pytest

from factory.payments.runtime.history import (
    PaymentHistoryEntry,
    RefundEntry,
)
from factory.payments.runtime.models import PaymentStatus, Currency


class TestPaymentHistoryEntry:
    """Tests for PaymentHistoryEntry model."""

    def test_create_entry(self):
        """Test creating a history entry."""
        entry = PaymentHistoryEntry(
            payment_id="pay_123",
            provider="stripe",
            provider_payment_id="pi_xxx",
            amount_cents=5000,
            currency=Currency.USD,
            status=PaymentStatus.COMPLETED,
        )
        assert entry.payment_id == "pay_123"
        assert entry.status == PaymentStatus.COMPLETED
        assert entry.amount_cents == 5000

    def test_entry_with_metadata(self):
        """Test entry with metadata."""
        entry = PaymentHistoryEntry(
            payment_id="pay_456",
            provider="stripe",
            provider_payment_id="pi_xxx",
            amount_cents=10000,
            currency=Currency.USD,
            status=PaymentStatus.COMPLETED,
            metadata={"order_id": "order_123"},
        )
        assert entry.metadata["order_id"] == "order_123"

    def test_entry_with_error(self):
        """Test entry with error."""
        entry = PaymentHistoryEntry(
            payment_id="pay_789",
            provider="stripe",
            provider_payment_id="pi_xxx",
            amount_cents=5000,
            currency=Currency.USD,
            status=PaymentStatus.FAILED,
            error="Card declined",
        )
        assert entry.status == PaymentStatus.FAILED
        assert entry.error == "Card declined"


class TestRefundEntry:
    """Tests for RefundEntry model."""

    def test_create_refund(self):
        """Test creating a refund entry."""
        refund = RefundEntry(
            refund_id="ref_123",
            payment_id="pay_123",
            provider="stripe",
            provider_refund_id="re_xxx",
            amount_cents=5000,
            status=PaymentStatus.REFUNDED,
        )
        assert refund.refund_id == "ref_123"
        assert refund.amount_cents == 5000

    def test_partial_refund(self):
        """Test partial refund entry."""
        refund = RefundEntry(
            refund_id="ref_456",
            payment_id="pay_123",
            provider="stripe",
            provider_refund_id="re_xxx",
            amount_cents=2500,  # Partial
            status=PaymentStatus.REFUNDED,
            reason="Customer request",
        )
        assert refund.amount_cents == 2500
        assert refund.reason == "Customer request"
