"""Allowlisted, public-safe output DTOs for Payments MCP tools."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import StrictModel
from .discovery import ProviderCapability, ProviderConfigProjection


class ProviderSummary(StrictModel):
    name: str
    type: str
    enabled: bool
    sandbox: bool
    connected: bool
    transaction_count: int
    total_amount_cents: int


class ProviderStats(StrictModel):
    name: str
    provider_type: str
    connected: bool
    transaction_count: int
    total_amount_cents: int
    refund_count: int
    total_refund_cents: int
    last_transaction_at: str | None


class PaymentSummary(StrictModel):
    payment_id: str
    provider: str
    provider_payment_id: str
    amount_cents: int
    currency: str
    status: str
    created_at: str


class RefundSummary(StrictModel):
    refund_id: str
    payment_id: str
    provider: str
    provider_refund_id: str
    amount_cents: int
    status: str
    created_at: str


class CapabilitiesOutput(StrictModel):
    schema_version: Literal["1.0.0"]
    running_mode: Literal["stdio"]
    providers: list[ProviderCapability]
    supported_providers: list[str]
    supported_currencies: list[str]
    authoring_enabled: bool
    feature_flags: dict[str, bool]


class HealthOutput(StrictModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    providers: list[ProviderStats]
    total_providers: int
    connected_count: int


class ConfigSchemaOutput(StrictModel):
    provider_config: ProviderConfigProjection
    provider_types: list[str]
    payment_statuses: list[str]
    currencies: list[str]


class RegistryOutput(StrictModel):
    providers: list[ProviderSummary]


class ProviderStatsOutput(StrictModel):
    found: bool
    stats: ProviderStats | None = None
    error: Literal["provider_not_found"] | None = None


class ListPaymentsOutput(StrictModel):
    payments: list[PaymentSummary]
    count: int
    total: int
    total_amount_cents: int
    error: Literal["invalid_status"] | None = None


class PaymentOutput(StrictModel):
    found: bool
    payment: PaymentSummary | None = None
    refunds: list[RefundSummary] = Field(default_factory=list)
    error: Literal["payment_not_found"] | None = None


class CreatePaymentOutput(StrictModel):
    success: bool
    payment_id: str | None = None
    provider_payment_id: str | None = None
    status: str | None = None
    amount_cents: int | None = None
    currency: str | None = None
    error: Literal["provider_not_found", "provider_disabled"] | None = None


class RefundPaymentOutput(StrictModel):
    success: bool
    refund_id: str | None = None
    payment_id: str | None = None
    amount_cents: int | None = None
    status: str | None = None
    error: Literal["payment_not_found", "payment_not_refundable", "refund_exceeds_payment"] | None = None


class WebhookOutput(StrictModel):
    processed: bool
    correlation_id: str | None = None
    event_type: str | None = None
    error: Literal["unknown_provider", "invalid_event_type"] | None = None


class AuthoringStatusOutput(StrictModel):
    enabled: bool


class ProviderMutationOutput(StrictModel):
    success: bool
    name: str | None = None
    provider_type: str | None = None
    updates: list[str] = Field(default_factory=list)
    error: Literal["authoring_disabled", "provider_not_found", "provider_invalid", "provider_exists"] | None = None
