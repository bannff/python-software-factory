"""Payment history tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol

from pydantic import BaseModel, Field

from .models import PaymentStatus, Currency


class PaymentHistoryEntry(BaseModel):
    """A payment history entry."""
    payment_id: str = Field(..., description="Internal payment ID")
    provider: str = Field(..., description="Provider name")
    provider_payment_id: str = Field(..., description="Provider's payment ID")
    amount_cents: int = Field(..., description="Amount in cents")
    currency: Currency = Field(..., description="Currency code")
    status: PaymentStatus = Field(..., description="Payment status")
    description: str | None = Field(None, description="Payment description")
    customer_id: str | None = Field(None, description="Customer ID")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    error: str | None = Field(None, description="Error message if failed")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None


class RefundEntry(BaseModel):
    """A refund entry."""
    refund_id: str = Field(..., description="Internal refund ID")
    payment_id: str = Field(..., description="Original payment ID")
    provider: str = Field(..., description="Provider name")
    provider_refund_id: str = Field(..., description="Provider's refund ID")
    amount_cents: int = Field(..., description="Refund amount in cents")
    status: PaymentStatus = Field(..., description="Refund status")
    reason: str | None = Field(None, description="Refund reason")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PaymentHistoryStore(Protocol):
    """Protocol for payment history storage."""

    def record_payment(self, entry: PaymentHistoryEntry) -> None:
        """Record a payment."""
        ...

    def get_payment(self, payment_id: str) -> PaymentHistoryEntry | None:
        """Get a payment by ID."""
        ...

    def record_refund(self, entry: RefundEntry) -> None:
        """Record a refund."""
        ...

    def get_refund(self, refund_id: str) -> RefundEntry | None:
        """Get a refund by ID."""
        ...


class InMemoryHistoryStore:
    """In-memory payment history store."""

    def __init__(self) -> None:
        self._payments: dict[str, PaymentHistoryEntry] = {}
        self._refunds: dict[str, RefundEntry] = {}
        self._payment_order: list[str] = []

    def record_payment(self, entry: PaymentHistoryEntry) -> None:
        """Record a payment."""
        self._payments[entry.payment_id] = entry
        if entry.payment_id not in self._payment_order:
            self._payment_order.append(entry.payment_id)

    def get_payment(self, payment_id: str) -> PaymentHistoryEntry | None:
        """Get a payment by ID."""
        return self._payments.get(payment_id)

    def record_refund(self, entry: RefundEntry) -> None:
        """Record a refund."""
        self._refunds[entry.refund_id] = entry

    def get_refund(self, refund_id: str) -> RefundEntry | None:
        """Get a refund by ID."""
        return self._refunds.get(refund_id)

    def list_by_provider(self, provider: str, limit: int = 100) -> list[PaymentHistoryEntry]:
        """List payments by provider."""
        return [
            p for p in self._payments.values()
            if p.provider == provider
        ][:limit]

    def list_by_status(self, status: PaymentStatus, limit: int = 100) -> list[PaymentHistoryEntry]:
        """List payments by status."""
        return [
            p for p in self._payments.values()
            if p.status == status
        ][:limit]

    def list_recent(self, limit: int = 100) -> list[PaymentHistoryEntry]:
        """List recent payments (most recent first)."""
        recent_ids = self._payment_order[-limit:][::-1]
        return [self._payments[pid] for pid in recent_ids]

    def get_refunds_for_payment(self, payment_id: str) -> list[RefundEntry]:
        """Get all refunds for a payment."""
        return [
            r for r in self._refunds.values()
            if r.payment_id == payment_id
        ]

    def get_total_amount(self, status: PaymentStatus | None = None) -> int:
        """Get total amount in cents."""
        payments = self._payments.values()
        if status:
            payments = [p for p in payments if p.status == status]
        return sum(p.amount_cents for p in payments)

    def count(self) -> int:
        """Count total payments."""
        return len(self._payments)

    def clear(self) -> None:
        """Clear all history."""
        self._payments.clear()
        self._refunds.clear()
        self._payment_order.clear()


# Global history store
_history_store: InMemoryHistoryStore | None = None


def get_history_store() -> InMemoryHistoryStore:
    """Get the global history store."""
    global _history_store
    if _history_store is None:
        _history_store = InMemoryHistoryStore()
    return _history_store
