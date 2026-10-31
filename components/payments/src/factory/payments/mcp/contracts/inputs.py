"""Flat, strict input DTOs for every Payments FastMCP tool."""
from __future__ import annotations

from typing import Any

from pydantic import Field

from .base import SafeJsonInput, SecretStr, StrictModel


class EmptyInput(StrictModel):
    """Strict DTO for a tool with no public inputs."""


class ProviderNameInput(StrictModel):
    provider_name: str = Field(min_length=1, max_length=128)


class ListPaymentsInput(StrictModel):
    provider: str | None = None
    status: str | None = None
    limit: int = Field(default=50, ge=1, le=100)


class PaymentIdInput(StrictModel):
    payment_id: str = Field(min_length=1, max_length=128)


class CreatePaymentInput(SafeJsonInput):
    provider_name: str = Field(min_length=1, max_length=128)
    amount_cents: int = Field(ge=1)
    currency: str = "USD"
    description: str | None = Field(default=None, max_length=512)
    customer_id: str | None = Field(default=None, max_length=128)
    payment_id: str | None = Field(default=None, max_length=128)
    metadata: dict[str, Any] | None = None


class RefundPaymentInput(StrictModel):
    payment_id: str = Field(min_length=1, max_length=128)
    amount_cents: int | None = Field(default=None, ge=1)
    reason: str | None = Field(default=None, max_length=512)


class ProcessWebhookInput(SafeJsonInput):
    provider: str = Field(min_length=1, max_length=64)
    payload: dict[str, Any]


class RegisterProviderInput(SafeJsonInput):
    name: str = Field(min_length=1, max_length=128)
    provider_type: str = Field(min_length=1, max_length=32)
    api_key: SecretStr | None = None
    public_key: SecretStr | None = None
    enabled: bool = True
    sandbox: bool = True
    options: dict[str, Any] | None = None


class UnregisterProviderInput(StrictModel):
    name: str = Field(min_length=1, max_length=128)


class UpdateProviderInput(StrictModel):
    name: str = Field(min_length=1, max_length=128)
    enabled: bool | None = None
    sandbox: bool | None = None
    api_key: SecretStr | None = None


__all__ = [
    "CreatePaymentInput", "EmptyInput", "ListPaymentsInput", "PaymentIdInput",
    "ProcessWebhookInput", "ProviderNameInput", "RefundPaymentInput",
    "RegisterProviderInput", "UnregisterProviderInput", "UpdateProviderInput",
]
