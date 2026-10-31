"""Webhook handling for payment providers."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, Field


class WebhookEventType(str, Enum):
    """Types of webhook events."""
    PAYMENT_COMPLETED = "payment.completed"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_PENDING = "payment.pending"
    REFUND_COMPLETED = "refund.completed"
    REFUND_FAILED = "refund.failed"
    DISPUTE_CREATED = "dispute.created"
    DISPUTE_RESOLVED = "dispute.resolved"
    UNKNOWN = "unknown"


class WebhookEvent(BaseModel):
    """A webhook event."""
    event_id: str = Field(..., description="Event ID")
    event_type: WebhookEventType = Field(..., description="Event type")
    provider: str = Field(..., description="Provider name")
    payload: dict[str, Any] = Field(default_factory=dict, description="Event payload")
    raw_payload: str | None = Field(None, description="Raw payload string")
    received_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# Stripe event type mapping
STRIPE_EVENT_MAP = {
    "payment_intent.succeeded": WebhookEventType.PAYMENT_COMPLETED,
    "payment_intent.payment_failed": WebhookEventType.PAYMENT_FAILED,
    "payment_intent.processing": WebhookEventType.PAYMENT_PENDING,
    "charge.refunded": WebhookEventType.REFUND_COMPLETED,
    "charge.refund.updated": WebhookEventType.REFUND_COMPLETED,
    "charge.dispute.created": WebhookEventType.DISPUTE_CREATED,
    "charge.dispute.closed": WebhookEventType.DISPUTE_RESOLVED,
}


class WebhookHandler:
    """Handler for payment webhooks."""

    def __init__(self) -> None:
        self._callbacks: dict[WebhookEventType, list[Callable[[WebhookEvent], None]]] = {}

    def register_callback(
        self,
        event_type: WebhookEventType,
        callback: Callable[[WebhookEvent], None],
    ) -> None:
        """Register a callback for an event type."""
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)

    def dispatch(self, event: WebhookEvent) -> None:
        """Dispatch an event to registered callbacks."""
        callbacks = self._callbacks.get(event.event_type, [])
        for callback in callbacks:
            try:
                callback(event)
            except Exception:
                pass  # Log error but don't fail

    def process_stripe_webhook(self, payload: dict[str, Any]) -> WebhookEvent:
        """Process a Stripe webhook payload."""
        stripe_type = payload.get("type", "")
        event_type = STRIPE_EVENT_MAP.get(stripe_type, WebhookEventType.UNKNOWN)
        
        data = payload.get("data", {}).get("object", {})
        
        # Extract relevant fields based on event type
        event_payload: dict[str, Any] = {}
        if "id" in data:
            event_payload["payment_id"] = data["id"]
        if "amount" in data:
            event_payload["amount_cents"] = data["amount"]
        if "currency" in data:
            event_payload["currency"] = data["currency"]
        if "last_payment_error" in data:
            event_payload["error"] = data["last_payment_error"].get("message")
        if "refunds" in data:
            refunds = data["refunds"].get("data", [])
            if refunds:
                event_payload["refund_id"] = refunds[0].get("id")
                event_payload["refund_amount"] = refunds[0].get("amount")
        
        return WebhookEvent(
            event_id=payload.get("id", f"evt_{datetime.now().timestamp()}"),
            event_type=event_type,
            provider="stripe",
            payload=event_payload,
        )

    def validate_stripe_signature(
        self,
        payload: bytes,
        signature: str,
        webhook_secret: str,
    ) -> bool:
        """Validate Stripe webhook signature."""
        try:
            import stripe
            stripe.Webhook.construct_event(payload, signature, webhook_secret)
            return True
        except Exception:
            return False


# Global webhook handler
_webhook_handler: WebhookHandler | None = None


def get_webhook_handler() -> WebhookHandler:
    """Get the global webhook handler."""
    global _webhook_handler
    if _webhook_handler is None:
        _webhook_handler = WebhookHandler()
    return _webhook_handler
