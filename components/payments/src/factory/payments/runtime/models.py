"""Core models for payments module."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, ConfigDict


class PaymentStatus(str, Enum):
    """Status of a payment."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    # Legacy alias used by older adapters/tests
    SUCCEEDED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class Currency(str, Enum):
    """Supported currencies."""
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    CAD = "CAD"
    AUD = "AUD"
    JPY = "JPY"


class Money(BaseModel):
    """A currency-aware money value object."""

    model_config = ConfigDict(frozen=True)

    amount: Decimal
    currency: Currency

    def __add__(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValueError("Cannot add Money with different currencies")
        return Money(amount=self.amount + other.amount, currency=self.currency)


class Transaction(BaseModel):
    transaction_id: str
    amount: Money
    status: PaymentStatus
    customer_id: str | None = None
    provider_id: str = ""
    provider_ref: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Customer(BaseModel):
    customer_id: str
    email: str
    name: str | None = None
    provider_refs: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class InvoiceItem(BaseModel):
    description: str
    unit_price: Money


class Invoice(BaseModel):
    invoice_id: str
    customer_id: str
    items: list[InvoiceItem]
    total: Money
    status: str
    due_date: datetime | None = None
    provider_id: str = ""
    provider_ref: str = ""
    hosted_invoice_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PaymentRequest(BaseModel):
    """A payment request."""
    payment_id: str | None = Field(None, description="Optional internal payment ID")
    amount_cents: int = Field(..., description="Amount in cents")
    currency: Currency = Field(Currency.USD, description="Currency code")
    description: str | None = Field(None, description="Payment description")
    customer_id: str | None = Field(None, description="Customer ID")
    customer_email: str | None = Field(None, description="Customer email")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")
    auto_capture: bool = Field(True, description="Auto-capture payment")
    return_url: str | None = Field(None, description="Return URL after payment")


class PaymentResult(BaseModel):
    """Result of a payment operation."""
    payment_id: str = Field(..., description="Internal payment ID")
    provider_payment_id: str = Field(..., description="Provider's payment ID")
    status: PaymentStatus = Field(..., description="Payment status")
    amount_cents: int | None = Field(None, description="Amount in cents")
    currency: Currency | None = Field(None, description="Currency")
    client_secret: str | None = Field(None, description="Client secret for frontend")
    error: str | None = Field(None, description="Error message if failed")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RefundResult(BaseModel):
    """Result of a refund operation."""
    refund_id: str = Field(..., description="Internal refund ID")
    payment_id: str = Field(..., description="Original payment ID")
    provider_refund_id: str | None = Field(None, description="Provider's refund ID")
    amount_cents: int | None = Field(None, description="Refund amount in cents")
    status: PaymentStatus = Field(..., description="Refund status")
    error: str | None = Field(None, description="Error message if failed")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ContextEnvelope(BaseModel):
    """Context envelope for cross-module composition."""
    tenant_id: str | None = None
    principal_id: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    customer_id: str | None = None
    agent_id: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)
