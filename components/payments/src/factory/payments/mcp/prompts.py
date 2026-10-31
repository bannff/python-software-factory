"""MCP prompts for payments module."""

from __future__ import annotations

from typing import Any

from .templates import (
    get_register_provider_prompt,
    get_debug_payment_prompt,
    get_configure_stripe_prompt,
)


def register(mcp: Any) -> None:
    """Register MCP prompts for payments."""

    @mcp.prompt()
    def register_provider(
        name: str = "my_provider",
        provider_type: str = "stripe",
        sandbox: bool = True,
    ) -> str:
        """Guide for registering a new payment provider.

        Args:
            name: Unique name for the provider
            provider_type: Type of provider (mock, stripe, paypal)
            sandbox: Whether to use sandbox/test mode
        """
        return get_register_provider_prompt(name, provider_type, sandbox)

    @mcp.prompt()
    def debug_payment(
        payment_id: str = "pay_xxx",
        status: str = "pending",
        provider: str = "stripe",
        amount_cents: int = 1000,
        currency: str = "USD",
    ) -> str:
        """Guide for debugging payment issues.

        Args:
            payment_id: The payment ID to debug
            status: Current payment status
            provider: Payment provider name
            amount_cents: Payment amount in cents
            currency: Payment currency
        """
        return get_debug_payment_prompt(
            payment_id, status, provider, amount_cents, currency
        )

    @mcp.prompt()
    def configure_stripe(name: str = "stripe", sandbox: bool = True) -> str:
        """Guide for configuring Stripe payment provider.

        Args:
            name: Name to register the provider as
            sandbox: Whether to use test mode
        """
        return get_configure_stripe_prompt(name, sandbox)
