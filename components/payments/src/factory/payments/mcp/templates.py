"""Public-safe prompt templates for Payments MCP prompts."""
from __future__ import annotations

REGISTER_PROVIDER_TEMPLATE = """# Register Payment Provider

Provider: {name} ({provider_type}); sandbox mode: {sandbox}.

1. Obtain credentials using the provider's approved secure channel.
2. Call `payments_authoring_register_provider` with the provider name, type, and
   secret input fields. Never put credentials in metadata, options, or chat text.
3. Verify safe aggregate status with `payments_get_provider_stats`.
"""

DEBUG_PAYMENT_TEMPLATE = """# Debug Payment: {payment_id}

Status: {status}; provider: {provider}; amount: {amount_cents} {currency}.

1. Call `payments_get_payment` for its safe status and refund summary.
2. Call `payments_health_check` and `payments_get_provider_stats`.
3. Investigate provider-side errors only through approved secure operational logs.
"""

CONFIGURE_STRIPE_TEMPLATE = """# Configure Stripe: {name}

Use sandbox mode: {sandbox}. Obtain Stripe credentials in its approved secure
channel, then submit them only to the secret input fields of
`payments_authoring_register_provider`. Do not paste credentials or card data
into prompts, metadata, options, or support tickets.
"""


def get_register_provider_prompt(name: str, provider_type: str, sandbox: bool = True) -> str:
    """Generate a provider registration guide without credential values."""
    return REGISTER_PROVIDER_TEMPLATE.format(name=name, provider_type=provider_type, sandbox=sandbox)


def get_debug_payment_prompt(payment_id: str, status: str, provider: str, amount_cents: int, currency: str) -> str:
    """Generate a safe payment debugging guide."""
    return DEBUG_PAYMENT_TEMPLATE.format(payment_id=payment_id, status=status, provider=provider, amount_cents=amount_cents, currency=currency)


def get_configure_stripe_prompt(name: str = "stripe", sandbox: bool = True) -> str:
    """Generate a Stripe configuration guide without credential values."""
    return CONFIGURE_STRIPE_TEMPLATE.format(name=name, sandbox=sandbox)
