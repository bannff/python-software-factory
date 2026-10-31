"""MCP server for payments module."""

from __future__ import annotations

import uuid
from typing import Any

from .authoring import get_authoring_tools
from .runtime.models import Currency
from .mcp import deterministic, operational, authoring, resources, prompts
from factory.mcp_utils.server import make_lazy_runner


def _register_tools(registry: Any) -> None:
    deterministic.register(registry)
    operational.register(registry)
    authoring.register(registry, get_authoring_tools)


def create_tool_catalog() -> Any:
    """Create the transport-neutral Payments tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    catalog = ToolCatalog("payments-module")
    _register_tools(catalog)
    resources.register(catalog)
    prompts.register(catalog)
    return catalog


def create_mcp_server() -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog()


def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for payments brick."""
    return {
        "name": "payments",
        "version": "1.0.0",
        "backends": ["stripe", "mock"],
        "features": ["payment_processing", "billing", "refunds", "webhooks"],
        "currencies_supported": [Currency.USD.value],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for payments brick."""
    return {"healthy": True, "provider": "stripe"}


def describe_config_schema() -> dict[str, Any]:
    """Describe payments configuration schema."""
    return {
        "type": "object",
        "properties": {
            "provider": {"type": "string", "enum": ["stripe", "mock"]},
            "credentials": {"description": "Accepted only through secret MCP inputs; never returned"},
        },
    }


get_mcp_server, main = make_lazy_runner(create_mcp_server)


def create_payment_intent(
    amount: float,
    currency: str = Currency.USD.value,
    customer_id: str | None = None,
) -> dict[str, Any]:
    """Compatibility wrapper for older tests."""
    amount_str = f"{amount:.2f}"
    is_decline = amount_str.endswith(".99")

    result: dict[str, Any] = {
        "id": f"pi_{uuid.uuid4().hex[:12]}",
        "status": "failed" if is_decline else "succeeded",
        "amount": {"amount": amount_str, "currency": currency},
        "customer_id": customer_id,
    }

    if is_decline:
        result["error_message"] = "Simulated card decline"

    return result


if __name__ == "__main__":
    main()
