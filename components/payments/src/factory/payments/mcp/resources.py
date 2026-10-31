"""Public-safe MCP resources for the Payments module."""
from __future__ import annotations

import json

from typing import Any

from .docs import get_doc, list_docs
from .deterministic import _payment
from ..runtime.history import get_history_store
from ..runtime.models import Currency, PaymentStatus
from ..runtime.registry import ProviderType, get_registry


def register(mcp: Any) -> None:
    """Register resources without exposing credentials or payment PII."""

    @mcp.resource("payments://schemas/provider-config")
    def get_provider_config_schema() -> str:
        return json.dumps({"type": "object", "properties": {
            "name": {"type": "string"}, "provider_type": {"enum": [item.value for item in ProviderType]},
            "enabled": {"type": "boolean"}, "sandbox": {"type": "boolean"},
        }}, indent=2)

    @mcp.resource("payments://schemas/payment-request")
    def get_payment_request_schema() -> str:
        return json.dumps({"type": "object", "properties": {
            "payment_id": {"type": "string"}, "amount_cents": {"type": "integer"},
            "currency": {"enum": [item.value for item in Currency]},
        }}, indent=2)

    @mcp.resource("payments://schemas/payment-result")
    def get_payment_result_schema() -> str:
        return json.dumps({"type": "object", "properties": {
            "payment_id": {"type": "string"}, "provider_payment_id": {"type": "string"},
            "status": {"enum": [item.value for item in PaymentStatus]},
            "amount_cents": {"type": "integer"}, "currency": {"enum": [item.value for item in Currency]},
        }}, indent=2)

    @mcp.resource("payments://schemas/enums")
    def get_enum_schemas() -> str:
        return json.dumps({"provider_types": [item.value for item in ProviderType], "payment_statuses": [item.value for item in PaymentStatus], "currencies": [item.value for item in Currency]}, indent=2)

    @mcp.resource("payments://docs")
    def list_documentation() -> str:
        return json.dumps({"available_docs": list_docs(), "resources": [
            "payments://docs/overview", "payments://docs/providers",
            "payments://docs/webhooks", "payments://docs/currencies",
        ]}, indent=2)

    @mcp.resource("payments://docs/overview")
    def get_overview_doc() -> str:
        return get_doc("overview") or "Documentation not found"

    @mcp.resource("payments://docs/providers")
    def get_providers_doc() -> str:
        return get_doc("providers") or "Documentation not found"

    @mcp.resource("payments://docs/webhooks")
    def get_webhooks_doc() -> str:
        return get_doc("webhooks") or "Documentation not found"

    @mcp.resource("payments://docs/currencies")
    def get_currencies_doc() -> str:
        return get_doc("currencies") or "Documentation not found"

    @mcp.resource("payments://providers")
    def get_providers_list() -> str:
        return json.dumps(get_registry().to_dict(), indent=2)

    @mcp.resource("payments://payments")
    def get_recent_payments() -> str:
        store = get_history_store()
        payments = [_payment(item).model_dump() for item in store.list_recent(50)]
        return json.dumps({"payments": payments, "count": len(payments), "total": store.count()}, indent=2)

    @mcp.resource("payments://stats")
    def get_payment_stats() -> str:
        store, registry = get_history_store(), get_registry()
        providers = [item for item in registry.to_dict()["providers"]]
        return json.dumps({"total_payments": store.count(), "total_amount_cents": store.get_total_amount(), "providers": providers}, indent=2)

    @mcp.resource("payments://factory")
    def get_factory_reference() -> str:
        return json.dumps({"brick": "payments", "namespace": "factory.payments", "foreman_tools": ["foreman_info", "foreman_guardian_check"], "related_bricks": ["auth", "events", "notification", "workflow"]}, indent=2)
