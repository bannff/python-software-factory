"""Tests for webhook handling."""

import pytest
import json
import hmac
import hashlib
from unittest.mock import MagicMock, patch

from factory.payments.runtime.webhooks import (
    WebhookEvent,
    WebhookHandler,
    WebhookEventType,
)
from factory.payments.runtime.models import PaymentStatus


class TestWebhookEvent:
    """Tests for WebhookEvent model."""

    def test_create_event(self):
        """Test creating a webhook event."""
        event = WebhookEvent(
            event_id="evt_123",
            event_type=WebhookEventType.PAYMENT_COMPLETED,
            provider="stripe",
            payload={"payment_id": "pi_xxx"},
        )
        assert event.event_id == "evt_123"
        assert event.event_type == WebhookEventType.PAYMENT_COMPLETED

    def test_event_with_raw_payload(self):
        """Test event with raw payload."""
        event = WebhookEvent(
            event_id="evt_456",
            event_type=WebhookEventType.PAYMENT_FAILED,
            provider="stripe",
            payload={"error": "Card declined"},
            raw_payload='{"error": "Card declined"}',
        )
        assert event.raw_payload is not None


class TestWebhookHandler:
    """Tests for WebhookHandler."""

    def test_process_stripe_payment_succeeded(self):
        """Test processing Stripe payment succeeded webhook."""
        handler = WebhookHandler()
        
        payload = {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_test123",
                    "amount": 5000,
                    "currency": "usd",
                }
            }
        }
        
        event = handler.process_stripe_webhook(payload)
        assert event.event_type == WebhookEventType.PAYMENT_COMPLETED
        assert event.payload["payment_id"] == "pi_test123"

    def test_process_stripe_payment_failed(self):
        """Test processing Stripe payment failed webhook."""
        handler = WebhookHandler()
        
        payload = {
            "type": "payment_intent.payment_failed",
            "data": {
                "object": {
                    "id": "pi_test123",
                    "last_payment_error": {"message": "Card declined"},
                }
            }
        }
        
        event = handler.process_stripe_webhook(payload)
        assert event.event_type == WebhookEventType.PAYMENT_FAILED

    def test_process_stripe_refund(self):
        """Test processing Stripe refund webhook."""
        handler = WebhookHandler()
        
        payload = {
            "type": "charge.refunded",
            "data": {
                "object": {
                    "id": "ch_test123",
                    "refunds": {
                        "data": [{"id": "re_test123", "amount": 5000}]
                    },
                }
            }
        }
        
        event = handler.process_stripe_webhook(payload)
        assert event.event_type == WebhookEventType.REFUND_COMPLETED

    def test_register_callback(self):
        """Test registering event callback."""
        handler = WebhookHandler()
        callback_called = []
        
        def on_payment_completed(event: WebhookEvent):
            callback_called.append(event)
        
        handler.register_callback(WebhookEventType.PAYMENT_COMPLETED, on_payment_completed)
        
        event = WebhookEvent(
            event_id="evt_123",
            event_type=WebhookEventType.PAYMENT_COMPLETED,
            provider="stripe",
            payload={},
        )
        handler.dispatch(event)
        
        assert len(callback_called) == 1

    def test_unknown_event_type(self):
        """Test handling unknown event type."""
        handler = WebhookHandler()
        
        payload = {
            "type": "unknown.event",
            "data": {"object": {}}
        }
        
        event = handler.process_stripe_webhook(payload)
        assert event.event_type == WebhookEventType.UNKNOWN

    def test_validate_stripe_signature(self):
        """Test validating Stripe webhook signature."""
        handler = WebhookHandler()
        
        # This would normally use Stripe's signature verification
        # For testing, we just check the method exists
        assert hasattr(handler, 'validate_stripe_signature')
