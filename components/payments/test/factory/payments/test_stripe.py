"""Tests for Stripe provider adapter."""

import pytest
from unittest.mock import MagicMock, patch

from factory.payments.runtime.providers.stripe_provider import (
    StripeConfig,
    StripeProvider,
)
from factory.payments.runtime.models import (
    PaymentRequest,
    PaymentStatus,
    Currency,
)


class TestStripeConfig:
    """Tests for StripeConfig model."""

    def test_create_config(self):
        """Test creating Stripe config."""
        config = StripeConfig(
            api_key="sk_test_xxx",
            webhook_secret="whsec_xxx",
        )
        assert config.api_key == "sk_test_xxx"
        assert config.webhook_secret == "whsec_xxx"

    def test_config_with_api_version(self):
        """Test config with explicit API version."""
        config = StripeConfig(
            api_key="sk_test_xxx",
            api_version="2023-10-16",
        )
        assert config.api_version == "2023-10-16"


class TestStripeProvider:
    """Tests for StripeProvider (mocked)."""

    def test_create_payment_intent_mocked(self):
        """Test creating payment intent with mocked Stripe."""
        config = StripeConfig(api_key="sk_test_xxx")
        provider = StripeProvider(config)
        
        with patch("stripe.PaymentIntent.create") as mock_create:
            mock_create.return_value = MagicMock(
                id="pi_test123",
                status="requires_payment_method",
                client_secret="pi_test123_secret_xxx",
            )
            
            request = PaymentRequest(
                amount_cents=5000,
                currency=Currency.USD,
                description="Test payment",
            )
            result = provider.create_payment(request)
            
            assert result.provider_payment_id == "pi_test123"
            assert result.status == PaymentStatus.PENDING

    def test_capture_payment_mocked(self):
        """Test capturing payment with mocked Stripe."""
        config = StripeConfig(api_key="sk_test_xxx")
        provider = StripeProvider(config)
        
        with patch("stripe.PaymentIntent.capture") as mock_capture:
            mock_capture.return_value = MagicMock(
                id="pi_test123",
                status="succeeded",
            )
            
            result = provider.capture_payment("pi_test123")
            assert result.status == PaymentStatus.COMPLETED

    def test_refund_payment_mocked(self):
        """Test refunding payment with mocked Stripe."""
        config = StripeConfig(api_key="sk_test_xxx")
        provider = StripeProvider(config)
        
        with patch("stripe.Refund.create") as mock_refund:
            mock_refund.return_value = MagicMock(
                id="re_test123",
                status="succeeded",
                amount=5000,
            )
            
            result = provider.refund_payment("pi_test123", amount_cents=5000)
            assert result.refund_id == "re_test123"
            assert result.status == PaymentStatus.REFUNDED

    def test_verify_webhook_mocked(self):
        """Test webhook verification with mocked Stripe."""
        config = StripeConfig(
            api_key="sk_test_xxx",
            webhook_secret="whsec_xxx",
        )
        provider = StripeProvider(config)
        
        with patch("stripe.Webhook.construct_event") as mock_construct:
            mock_construct.return_value = {
                "type": "payment_intent.succeeded",
                "data": {"object": {"id": "pi_test123"}},
            }
            
            event = provider.verify_webhook(
                payload=b'{"type": "payment_intent.succeeded"}',
                signature="test_sig",
            )
            assert event["type"] == "payment_intent.succeeded"

    def test_get_payment_mocked(self):
        """Test getting payment with mocked Stripe."""
        config = StripeConfig(api_key="sk_test_xxx")
        provider = StripeProvider(config)
        
        with patch("stripe.PaymentIntent.retrieve") as mock_retrieve:
            mock_retrieve.return_value = MagicMock(
                id="pi_test123",
                status="succeeded",
                amount=5000,
                currency="usd",
            )
            
            result = provider.get_payment("pi_test123")
            assert result is not None
            assert result["id"] == "pi_test123"

    def test_list_payments_mocked(self):
        """Test listing payments with mocked Stripe."""
        config = StripeConfig(api_key="sk_test_xxx")
        provider = StripeProvider(config)
        
        with patch("stripe.PaymentIntent.list") as mock_list:
            mock_list.return_value = MagicMock(
                data=[
                    MagicMock(id="pi_1", status="succeeded"),
                    MagicMock(id="pi_2", status="succeeded"),
                ],
                has_more=False,
            )
            
            result = provider.list_payments(limit=10)
            assert len(result) == 2
