"""Behavioral MCP acceptance tests for isolated mock and non-mock payment flows."""
from __future__ import annotations

import asyncio

import pytest

from factory.payments.runtime.history import get_history_store
from factory.payments.runtime.registry import reset_registry
from factory.payments.server import create_mcp_server


def _tool(name: str):
    return asyncio.run(create_mcp_server().get_tool(name)).fn


@pytest.fixture(autouse=True)
def _isolated_payment_state(monkeypatch: pytest.MonkeyPatch):
    """Reset the Payments-owned in-memory state around every MCP scenario."""
    monkeypatch.setenv("PAYMENTS_ENABLE_AUTHORING_TOOLS", "1")
    reset_registry()
    get_history_store().clear()
    yield
    reset_registry()
    get_history_store().clear()


def _register(name: str, provider_type: str, *, enabled: bool = True) -> None:
    result = _tool("payments_authoring_register_provider")(
        name=name, provider_type=provider_type, enabled=enabled
    )
    assert result.ok and result.data.success


def test_mock_payment_partial_refund_and_expected_negatives() -> None:
    _register("mock-provider", "mock")
    created = _tool("payments_create_payment")(
        provider_name="mock-provider", amount_cents=500, payment_id="mock-payment"
    )
    assert created.ok and created.data.status == "completed"

    refunded = _tool("payments_refund_payment")(
        payment_id="mock-payment", amount_cents=200
    )
    assert refunded.ok and refunded.data.success
    excess = _tool("payments_refund_payment")(
        payment_id="mock-payment", amount_cents=301
    )
    missing = _tool("payments_refund_payment")(payment_id="missing")
    assert excess.ok and excess.data.error == "refund_exceeds_payment"
    assert missing.ok and missing.data.error == "payment_not_found"


def test_non_mock_payment_is_pending_and_not_refundable() -> None:
    _register("stripe-provider", "stripe")
    created = _tool("payments_create_payment")(
        provider_name="stripe-provider", amount_cents=500, payment_id="stripe-payment"
    )
    refund = _tool("payments_refund_payment")(payment_id="stripe-payment")
    assert created.ok and created.data.status == "pending"
    assert refund.ok and refund.data.error == "payment_not_refundable"


def test_state_isolation_removes_prior_provider_and_history() -> None:
    _register("isolated-provider", "mock")
    _tool("payments_create_payment")(
        provider_name="isolated-provider", amount_cents=100, payment_id="isolated-payment"
    )
    reset_registry()
    get_history_store().clear()

    registry = _tool("payments_get_provider_registry")()
    payment = _tool("payments_get_payment")(payment_id="isolated-payment")
    assert registry.ok and registry.data.providers == []
    assert payment.ok and not payment.data.found and payment.data.error == "payment_not_found"
