"""Tests for InMemoryHistoryStore."""

import pytest

from factory.payments.runtime.history import (
    PaymentHistoryEntry,
    RefundEntry,
    InMemoryHistoryStore,
)
from factory.payments.runtime.models import PaymentStatus, Currency


class TestInMemoryHistoryStore:
    """Tests for InMemoryHistoryStore."""

    def test_record_payment(self):
        """Test recording a payment."""
        store = InMemoryHistoryStore()
        entry = PaymentHistoryEntry(
            payment_id="pay_123",
            provider="mock",
            provider_payment_id="mock_xxx",
            amount_cents=5000,
            currency=Currency.USD,
            status=PaymentStatus.COMPLETED,
        )
        store.record_payment(entry)

        retrieved = store.get_payment("pay_123")
        assert retrieved is not None
        assert retrieved.payment_id == "pay_123"

    def test_get_nonexistent_payment(self):
        """Test getting non-existent payment."""
        store = InMemoryHistoryStore()
        assert store.get_payment("nonexistent") is None

    def test_record_refund(self):
        """Test recording a refund."""
        store = InMemoryHistoryStore()
        refund = RefundEntry(
            refund_id="ref_123",
            payment_id="pay_123",
            provider="mock",
            provider_refund_id="mock_ref",
            amount_cents=5000,
            status=PaymentStatus.REFUNDED,
        )
        store.record_refund(refund)

        retrieved = store.get_refund("ref_123")
        assert retrieved is not None

    def test_list_by_provider(self):
        """Test listing payments by provider."""
        store = InMemoryHistoryStore()
        store.record_payment(
            PaymentHistoryEntry(
                payment_id="p1",
                provider="stripe",
                provider_payment_id="pi_1",
                amount_cents=1000,
                currency=Currency.USD,
                status=PaymentStatus.COMPLETED,
            )
        )
        store.record_payment(
            PaymentHistoryEntry(
                payment_id="p2",
                provider="stripe",
                provider_payment_id="pi_2",
                amount_cents=2000,
                currency=Currency.USD,
                status=PaymentStatus.COMPLETED,
            )
        )
        store.record_payment(
            PaymentHistoryEntry(
                payment_id="p3",
                provider="mock",
                provider_payment_id="mock_1",
                amount_cents=3000,
                currency=Currency.USD,
                status=PaymentStatus.COMPLETED,
            )
        )

        stripe_payments = store.list_by_provider("stripe")
        assert len(stripe_payments) == 2

    def test_list_by_status(self):
        """Test listing payments by status."""
        store = InMemoryHistoryStore()
        store.record_payment(
            PaymentHistoryEntry(
                payment_id="p1",
                provider="mock",
                provider_payment_id="m1",
                amount_cents=1000,
                currency=Currency.USD,
                status=PaymentStatus.COMPLETED,
            )
        )
        store.record_payment(
            PaymentHistoryEntry(
                payment_id="p2",
                provider="mock",
                provider_payment_id="m2",
                amount_cents=2000,
                currency=Currency.USD,
                status=PaymentStatus.FAILED,
            )
        )

        completed = store.list_by_status(PaymentStatus.COMPLETED)
        assert len(completed) == 1

    def test_list_recent(self):
        """Test listing recent payments."""
        store = InMemoryHistoryStore()
        for i in range(10):
            store.record_payment(
                PaymentHistoryEntry(
                    payment_id=f"p{i}",
                    provider="mock",
                    provider_payment_id=f"m{i}",
                    amount_cents=1000,
                    currency=Currency.USD,
                    status=PaymentStatus.COMPLETED,
                )
            )

        recent = store.list_recent(limit=5)
        assert len(recent) == 5
        assert recent[0].payment_id == "p9"  # Most recent first

    def test_get_refunds_for_payment(self):
        """Test getting refunds for a payment."""
        store = InMemoryHistoryStore()
        store.record_refund(
            RefundEntry(
                refund_id="r1",
                payment_id="pay_123",
                provider="mock",
                provider_refund_id="mr1",
                amount_cents=1000,
                status=PaymentStatus.REFUNDED,
            )
        )
        store.record_refund(
            RefundEntry(
                refund_id="r2",
                payment_id="pay_123",
                provider="mock",
                provider_refund_id="mr2",
                amount_cents=2000,
                status=PaymentStatus.REFUNDED,
            )
        )
        store.record_refund(
            RefundEntry(
                refund_id="r3",
                payment_id="pay_456",
                provider="mock",
                provider_refund_id="mr3",
                amount_cents=500,
                status=PaymentStatus.REFUNDED,
            )
        )

        refunds = store.get_refunds_for_payment("pay_123")
        assert len(refunds) == 2

    def test_get_total_amount(self):
        """Test getting total amount."""
        store = InMemoryHistoryStore()
        store.record_payment(
            PaymentHistoryEntry(
                payment_id="p1",
                provider="mock",
                provider_payment_id="m1",
                amount_cents=5000,
                currency=Currency.USD,
                status=PaymentStatus.COMPLETED,
            )
        )
        store.record_payment(
            PaymentHistoryEntry(
                payment_id="p2",
                provider="mock",
                provider_payment_id="m2",
                amount_cents=3000,
                currency=Currency.USD,
                status=PaymentStatus.COMPLETED,
            )
        )

        total = store.get_total_amount()
        assert total == 8000
