"""Deterministic, typed MCP tools for Payments."""
from __future__ import annotations

from typing import Any
from factory.mcp_utils.interface import ToolResult, deterministic, ok

from ..authoring import is_authoring_enabled
from ..runtime.history import get_history_store
from ..runtime.models import Currency, PaymentStatus
from ..runtime.registry import ProviderType, get_registry
from .contracts.discovery import PROVIDER_CAPABILITIES, provider_config_projection
from .contracts.inputs import EmptyInput, ListPaymentsInput, PaymentIdInput, ProviderNameInput
from .contracts.outputs import (
    CapabilitiesOutput, ConfigSchemaOutput, HealthOutput, ListPaymentsOutput,
    PaymentOutput, PaymentSummary, ProviderStats, ProviderStatsOutput,
    ProviderSummary, RefundSummary, RegistryOutput,
)


def _provider_stats(stats: object) -> ProviderStats:
    return ProviderStats.model_validate(stats, from_attributes=True)


def _payment(entry: object) -> PaymentSummary:
    return PaymentSummary.model_validate(entry, from_attributes=True)


def _refund(entry: object) -> RefundSummary:
    return RefundSummary.model_validate(entry, from_attributes=True)


def register(mcp: Any) -> None:
    """Register deterministic Payments tools."""

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def payments_get_capabilities() -> ToolResult[CapabilitiesOutput]:
        return ok(CapabilitiesOutput(
            schema_version="1.0.0",
            running_mode="stdio",
            providers=PROVIDER_CAPABILITIES,
            supported_providers=[item.value for item in ProviderType],
            supported_currencies=[item.value for item in Currency],
            authoring_enabled=is_authoring_enabled(),
            feature_flags={"payment_history": True, "refunds": True, "webhooks": True, "stripe_support": True},
        ))

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def payments_health_check() -> ToolResult[HealthOutput]:
        registry = get_registry()
        providers = [
            _provider_stats(stats) for name in registry.list_providers()
            if (stats := registry.get_stats(name)) is not None
        ]
        connected = sum(item.connected for item in providers)
        status = "healthy" if connected == len(providers) else "degraded" if connected else "unhealthy"
        return ok(HealthOutput(status=status, providers=providers, total_providers=len(providers), connected_count=connected))

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def payments_describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        return ok(ConfigSchemaOutput(
            provider_config=provider_config_projection(),
            provider_types=[item.value for item in ProviderType],
            payment_statuses=[item.value for item in PaymentStatus], currencies=[item.value for item in Currency],
        ))

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=RegistryOutput)
    def payments_get_provider_registry() -> ToolResult[RegistryOutput]:
        registry = get_registry()
        providers = [ProviderSummary(**item) for item in registry.to_dict()["providers"]]
        return ok(RegistryOutput(providers=providers))

    @mcp.tool()
    @deterministic(input_model=ProviderNameInput, output_model=ProviderStatsOutput)
    def payments_get_provider_stats(provider_name: str) -> ToolResult[ProviderStatsOutput]:
        stats = get_registry().get_stats(provider_name)
        if stats is None:
            return ok(ProviderStatsOutput(found=False, error="provider_not_found"))
        return ok(ProviderStatsOutput(found=True, stats=_provider_stats(stats)))

    @mcp.tool()
    @deterministic(input_model=ListPaymentsInput, output_model=ListPaymentsOutput)
    def payments_list_payments(provider: str | None = None, status: str | None = None, limit: int = 50) -> ToolResult[ListPaymentsOutput]:
        store = get_history_store()
        if provider:
            entries, error = store.list_by_provider(provider, limit), None
        elif status:
            try:
                entries, error = store.list_by_status(PaymentStatus(status), limit), None
            except ValueError:
                entries, error = [], "invalid_status"
        else:
            entries, error = store.list_recent(limit), None
        return ok(ListPaymentsOutput(payments=[_payment(item) for item in entries], count=len(entries), total=store.count(), total_amount_cents=store.get_total_amount(), error=error))

    @mcp.tool()
    @deterministic(input_model=PaymentIdInput, output_model=PaymentOutput)
    def payments_get_payment(payment_id: str) -> ToolResult[PaymentOutput]:
        store = get_history_store()
        entry = store.get_payment(payment_id)
        if entry is None:
            return ok(PaymentOutput(found=False, error="payment_not_found"))
        return ok(PaymentOutput(payment=_payment(entry), found=True, refunds=[_refund(item) for item in store.get_refunds_for_payment(payment_id)]))
