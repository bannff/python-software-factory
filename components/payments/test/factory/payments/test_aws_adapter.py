"""Tests for AWS Marketplace Metering payments adapter."""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from factory.payments.runtime.models import (
    Currency, Money, PaymentStatus,
)


@pytest.fixture
def mock_boto3():
    with patch("boto3.client") as mc:
        mc.return_value = MagicMock()
        yield mc


@pytest.fixture
def provider(mock_boto3):
    from factory.payments.runtime.providers.aws import AWSMarketplaceProvider

    return AWSMarketplaceProvider(product_code="prod-abc123")


@pytest.fixture
def money():
    return Money(amount=Decimal("100"), currency=Currency.USD)


def test_invalid_product_code(mock_boto3):
    from factory.payments.runtime.providers.aws import AWSMarketplaceProvider

    with pytest.raises(ValueError, match="Invalid product_code"):
        AWSMarketplaceProvider(product_code="bad code!!!")


def test_provider_id(provider):
    assert provider.provider_id == "aws-marketplace"


def test_health_check_ok(provider):
    provider._client.meter_usage.return_value = {}
    assert provider.health_check() is True


def test_health_check_error(provider):
    provider._client.meter_usage.side_effect = Exception("fail")
    assert provider.health_check() is False


def test_create_payment_intent_success(provider, money):
    provider._client.meter_usage.return_value = {"MeteringRecordId": "mr-1"}
    txn = provider.create_payment_intent(money, customer_id="c1")
    assert txn.status == PaymentStatus.COMPLETED
    assert txn.provider_ref == "mr-1"
    assert txn.customer_id == "c1"


def test_create_payment_intent_failure(provider, money):
    provider._client.meter_usage.side_effect = Exception("meter fail")
    txn = provider.create_payment_intent(money)
    assert txn.status == PaymentStatus.FAILED
    assert "meter fail" in txn.error_message


def test_create_payment_intent_custom_dimension(provider, money):
    provider._client.meter_usage.return_value = {"MeteringRecordId": "mr-2"}
    txn = provider.create_payment_intent(
        money, metadata={"usage_dimension": "storage_gb"},
    )
    call_kwargs = provider._client.meter_usage.call_args[1]
    assert call_kwargs["UsageDimension"] == "storage_gb"


def test_get_transaction_found(provider, money):
    provider._client.meter_usage.return_value = {"MeteringRecordId": "mr-1"}
    provider.create_payment_intent(money)
    txn = provider.get_transaction("mr-1")
    assert txn is not None
    assert txn.provider_ref == "mr-1"


def test_get_transaction_not_found(provider):
    assert provider.get_transaction("nonexistent") is None


def test_refund_not_supported(provider, money):
    provider._client.meter_usage.return_value = {"MeteringRecordId": "mr-1"}
    provider.create_payment_intent(money)
    refunded = provider.refund_transaction("mr-1")
    assert refunded.status == PaymentStatus.FAILED
    assert "not supported" in refunded.error_message.lower()


def test_refund_missing_transaction(provider):
    with pytest.raises(ValueError, match="Transaction not found"):
        provider.refund_transaction("nonexistent")


def test_create_customer(provider):
    c = provider.create_customer("[email protected]", name="Alice")
    assert c.email == "[email protected]"
    assert c.name == "Alice"
    assert c.customer_id.startswith("cus_")


def test_create_invoice(provider, money):
    inv = provider.create_invoice("c1", money, "Monthly usage")
    assert inv.invoice_id.startswith("inv_")
    assert inv.status == "not_supported"
    assert inv.customer_id == "c1"


def test_infrastructure_spec(provider):
    spec = provider.infrastructure_spec()
    assert spec["service"] == "marketplace-metering"
    assert spec["props"]["product_code"] == "prod-abc123"
