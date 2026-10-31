"""Accurate, public-safe documentation for Payments MCP resources."""
from __future__ import annotations

OVERVIEW_DOC = """# Payments Brick

Payments provides provider registration, in-memory payment history, refunds, and
webhook dispatch. Each public tool preserves flat keyword arguments, validates ingress
with a strict Payments-local Pydantic v2 DTO, and returns `ToolResult[OutputDTO]`.
Check `result.ok` before reading a successful typed payload from `result.data`;
expected domain outcomes remain typed data, while only unexpected faults fail the envelope.

Provider credentials are accepted only through secret input fields and are never
returned by tools or resources. Payment history output deliberately excludes
customer identifiers, descriptions, metadata, and provider errors.

## MCP Tools

- Deterministic: capabilities, health, configuration choices, provider registry
  and stats, payment listing, and payment lookup.
- Operational: create a payment, refund a payment, and parse/dispatch a webhook.
- Authoring: authoring status plus provider register, unregister, and update.
"""

PROVIDERS_DOC = """# Payment Providers

Supported provider types are Mock, Stripe, and planned PayPal. Provider listing
and statistics expose only operational status and aggregate counters. Register
credentials through a secure caller channel; do not place them in metadata,
options, logs, or support requests.
"""

WEBHOOKS_DOC = """# Webhook Processing

`payments_process_webhook` currently parses the supplied Stripe-shaped payload
and dispatches the derived event to local callbacks. It does **not** verify a
signature and does **not** change payment status. The public response contains
`processed`, an optional server-generated opaque `correlation_id`, optional safe
`event_type`, and only stable `unknown_provider` or `invalid_event_type` errors;
payload contents and untrusted event identifiers are never returned.
"""

CURRENCIES_DOC = """# Currency Support

Amounts use the smallest unit (cents). Supported currency codes are exposed by
`payments_describe_config_schema`; this brick does not perform conversion.
"""

DOCS = {"overview": OVERVIEW_DOC, "providers": PROVIDERS_DOC, "webhooks": WEBHOOKS_DOC, "currencies": CURRENCIES_DOC}


def get_doc(name: str) -> str | None:
    """Get documentation by name."""
    return DOCS.get(name)


def list_docs() -> list[str]:
    """List available documentation."""
    return list(DOCS)
