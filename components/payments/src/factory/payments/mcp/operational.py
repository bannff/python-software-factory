"""Operational, typed MCP tools for Payments."""
from __future__ import annotations

import uuid
from typing import Any
from factory.mcp_utils.interface import ToolResult, ok, operational

from ..runtime.history import PaymentHistoryEntry, RefundEntry, get_history_store
from ..runtime.models import Currency, PaymentStatus
from ..runtime.registry import ProviderType, get_registry
from ..runtime.webhooks import STRIPE_EVENT_MAP, get_webhook_handler
from .contracts.inputs import CreatePaymentInput, ProcessWebhookInput, RefundPaymentInput
from .contracts.outputs import CreatePaymentOutput, RefundPaymentOutput, WebhookOutput


def register(mcp: Any) -> None:
    """Register operational Payments tools."""

    @mcp.tool()
    @operational(input_model=CreatePaymentInput, output_model=CreatePaymentOutput)
    def payments_create_payment(
        provider_name: str, amount_cents: int, currency: str = "USD", description: str | None = None,
        customer_id: str | None = None, payment_id: str | None = None, metadata: dict[str, Any] | None = None,
    ) -> ToolResult[CreatePaymentOutput]:
        registry = get_registry()
        config = registry.get(provider_name)
        if config is None:
            return ok(CreatePaymentOutput(success=False, error="provider_not_found"))
        if not config.enabled:
            return ok(CreatePaymentOutput(success=False, error="provider_disabled"))
        payment_id = payment_id or f"pay_{uuid.uuid4().hex[:16]}"
        is_mock = config.provider_type == ProviderType.MOCK
        provider_payment_id = f"{'mock' if is_mock else config.provider_type.value}_{uuid.uuid4().hex[:8]}"
        status = PaymentStatus.COMPLETED if is_mock else PaymentStatus.PENDING
        try:
            parsed_currency = Currency(currency)
        except ValueError:
            parsed_currency = Currency.USD
        get_history_store().record_payment(PaymentHistoryEntry(
            payment_id=payment_id, provider=provider_name, provider_payment_id=provider_payment_id,
            amount_cents=amount_cents, currency=parsed_currency, status=status, description=description,
            customer_id=customer_id, metadata=metadata or {},
        ))
        registry.record_transaction(provider_name, payment_id, amount_cents)
        return ok(CreatePaymentOutput(success=True, payment_id=payment_id, provider_payment_id=provider_payment_id, status=status.value, amount_cents=amount_cents, currency=currency))

    @mcp.tool()
    @operational(input_model=RefundPaymentInput, output_model=RefundPaymentOutput)
    def payments_refund_payment(payment_id: str, amount_cents: int | None = None, reason: str | None = None) -> ToolResult[RefundPaymentOutput]:
        store = get_history_store()
        payment = store.get_payment(payment_id)
        if payment is None:
            return ok(RefundPaymentOutput(success=False, error="payment_not_found"))
        if payment.status not in (PaymentStatus.COMPLETED, PaymentStatus.PARTIALLY_REFUNDED):
            return ok(RefundPaymentOutput(success=False, error="payment_not_refundable"))
        amount_cents = amount_cents if amount_cents is not None else payment.amount_cents
        if sum(refund.amount_cents for refund in store.get_refunds_for_payment(payment_id)) + amount_cents > payment.amount_cents:
            return ok(RefundPaymentOutput(success=False, error="refund_exceeds_payment"))
        refund_id = f"ref_{uuid.uuid4().hex[:16]}"
        store.record_refund(RefundEntry(refund_id=refund_id, payment_id=payment_id, provider=payment.provider,
            provider_refund_id=f"mock_ref_{uuid.uuid4().hex[:8]}", amount_cents=amount_cents,
            status=PaymentStatus.REFUNDED, reason=reason))
        get_registry().record_refund(payment.provider, amount_cents)
        return ok(RefundPaymentOutput(success=True, refund_id=refund_id, payment_id=payment_id, amount_cents=amount_cents, status=PaymentStatus.REFUNDED.value))

    @mcp.tool()
    @operational(input_model=ProcessWebhookInput, output_model=WebhookOutput)
    def payments_process_webhook(provider: str, payload: dict[str, Any]) -> ToolResult[WebhookOutput]:
        """Parse and dispatch an unverified webhook; it never changes payment status."""
        if provider != "stripe":
            return ok(WebhookOutput(processed=False, error="unknown_provider"))
        stripe_type = payload.get("type")
        if not isinstance(stripe_type, str) or stripe_type not in STRIPE_EVENT_MAP:
            return ok(WebhookOutput(processed=False, error="invalid_event_type"))
        handler = get_webhook_handler()
        event = handler.process_stripe_webhook(payload)
        handler.dispatch(event)
        return ok(WebhookOutput(
            processed=True,
            correlation_id=f"wh_{uuid.uuid4().hex}",
            event_type=event.event_type.value,
        ))
