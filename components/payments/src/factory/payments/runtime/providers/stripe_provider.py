"""Stripe payment provider adapter."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from ..models import (
    PaymentRequest,
    PaymentResult,
    PaymentStatus,
    RefundResult,
)
from ..ports import PaymentGateway

logger = logging.getLogger(__name__)


class StripeConfig(BaseModel):
    """Configuration for Stripe provider."""
    api_key: str = Field(..., description="Stripe secret API key")
    webhook_secret: str | None = Field(None, description="Webhook signing secret")
    api_version: str | None = Field(None, description="Stripe API version")


class StripeProvider(PaymentGateway):
    """Stripe payment provider implementation."""

    def __init__(self, config: StripeConfig) -> None:
        self._config = config
        self._stripe: Any = None
        self._initialize()

    def _initialize(self) -> None:
        """Initialize Stripe SDK."""
        try:
            import stripe
            stripe.api_key = self._config.api_key
            if self._config.api_version:
                stripe.api_version = self._config.api_version
            self._stripe = stripe
            logger.info("Stripe provider initialized")
        except ImportError:
            logger.warning("Stripe SDK not installed. Install with: pip install stripe")
            self._stripe = None

    def create_payment(self, request: PaymentRequest) -> PaymentResult:
        """Create a payment intent."""
        if self._stripe is None:
            return PaymentResult(
                payment_id=request.payment_id or "unknown",
                provider_payment_id="",
                status=PaymentStatus.FAILED,
                error="Stripe SDK not installed",
            )
        
        try:
            intent = self._stripe.PaymentIntent.create(
                amount=request.amount_cents,
                currency=request.currency.value.lower(),
                description=request.description,
                metadata=request.metadata or {},
                capture_method="automatic" if request.auto_capture else "manual",
            )
            
            return PaymentResult(
                payment_id=request.payment_id or intent.id,
                provider_payment_id=intent.id,
                status=PaymentStatus.PENDING,
                client_secret=intent.client_secret,
            )
        except Exception as e:
            logger.error(f"Stripe create payment failed: {e}")
            return PaymentResult(
                payment_id=request.payment_id or "unknown",
                provider_payment_id="",
                status=PaymentStatus.FAILED,
                error=str(e),
            )

    def capture_payment(self, provider_payment_id: str) -> PaymentResult:
        """Capture a payment intent."""
        if self._stripe is None:
            return PaymentResult(
                payment_id="",
                provider_payment_id=provider_payment_id,
                status=PaymentStatus.FAILED,
                error="Stripe SDK not installed",
            )
        
        try:
            intent = self._stripe.PaymentIntent.capture(provider_payment_id)
            
            status = PaymentStatus.COMPLETED if intent.status == "succeeded" else PaymentStatus.PENDING
            
            return PaymentResult(
                payment_id=intent.id,
                provider_payment_id=intent.id,
                status=status,
            )
        except Exception as e:
            logger.error(f"Stripe capture failed: {e}")
            return PaymentResult(
                payment_id="",
                provider_payment_id=provider_payment_id,
                status=PaymentStatus.FAILED,
                error=str(e),
            )

    def refund_payment(
        self,
        provider_payment_id: str,
        amount_cents: int | None = None,
        reason: str | None = None,
    ) -> RefundResult:
        """Refund a payment."""
        if self._stripe is None:
            return RefundResult(
                refund_id="",
                payment_id=provider_payment_id,
                status=PaymentStatus.FAILED,
                error="Stripe SDK not installed",
            )
        
        try:
            refund_params: dict[str, Any] = {
                "payment_intent": provider_payment_id,
            }
            if amount_cents:
                refund_params["amount"] = amount_cents
            if reason:
                refund_params["reason"] = reason
            
            refund = self._stripe.Refund.create(**refund_params)
            
            return RefundResult(
                refund_id=refund.id,
                payment_id=provider_payment_id,
                provider_refund_id=refund.id,
                amount_cents=refund.amount,
                status=PaymentStatus.REFUNDED if refund.status == "succeeded" else PaymentStatus.PENDING,
            )
        except Exception as e:
            logger.error(f"Stripe refund failed: {e}")
            return RefundResult(
                refund_id="",
                payment_id=provider_payment_id,
                status=PaymentStatus.FAILED,
                error=str(e),
            )

    def get_payment(self, provider_payment_id: str) -> dict[str, Any] | None:
        """Get payment details."""
        if self._stripe is None:
            return None
        
        try:
            intent = self._stripe.PaymentIntent.retrieve(provider_payment_id)
            return {
                "id": intent.id,
                "status": intent.status,
                "amount": intent.amount,
                "currency": intent.currency,
            }
        except Exception as e:
            logger.error(f"Stripe get payment failed: {e}")
            return None

    def list_payments(self, limit: int = 10) -> list[dict[str, Any]]:
        """List recent payments."""
        if self._stripe is None:
            return []
        
        try:
            intents = self._stripe.PaymentIntent.list(limit=limit)
            return [
                {"id": i.id, "status": i.status, "amount": i.amount}
                for i in intents.data
            ]
        except Exception as e:
            logger.error(f"Stripe list payments failed: {e}")
            return []

    def verify_webhook(self, payload: bytes, signature: str) -> dict[str, Any] | None:
        """Verify and parse webhook payload."""
        if self._stripe is None or not self._config.webhook_secret:
            return None
        
        try:
            event = self._stripe.Webhook.construct_event(
                payload, signature, self._config.webhook_secret
            )
            return event
        except Exception as e:
            logger.error(f"Stripe webhook verification failed: {e}")
            return None
