"""Property tests for isolated Payments MCP payment/refund round trips."""
from __future__ import annotations

import asyncio
import os

from hypothesis import given, settings, strategies as st

from factory.payments.runtime.history import get_history_store
from factory.payments.runtime.registry import reset_registry
from factory.payments.server import create_mcp_server


def _tool(name: str):
    return asyncio.run(create_mcp_server().get_tool(name)).fn


def _reset_state() -> None:
    reset_registry()
    get_history_store().clear()


@settings(max_examples=50, deadline=None)
@given(
    amount_cents=st.integers(min_value=1, max_value=100_000),
    refund_cents=st.integers(min_value=1, max_value=100_000),
)
def test_mock_payment_refund_roundtrip_isolated(
    amount_cents: int, refund_cents: int
) -> None:
    """A valid partial refund remains visible and exact for every amount pair."""
    refund_cents = min(refund_cents, amount_cents)
    prior = os.environ.get("PAYMENTS_ENABLE_AUTHORING_TOOLS")
    os.environ["PAYMENTS_ENABLE_AUTHORING_TOOLS"] = "1"
    _reset_state()
    try:
        registered = _tool("payments_authoring_register_provider")(
            name="property-mock", provider_type="mock"
        )
        created = _tool("payments_create_payment")(
            provider_name="property-mock",
            amount_cents=amount_cents,
            payment_id="property-payment",
        )
        refunded = _tool("payments_refund_payment")(
            payment_id="property-payment", amount_cents=refund_cents
        )
        retrieved = _tool("payments_get_payment")(payment_id="property-payment")

        assert registered.ok and registered.data.success
        assert created.ok and created.data.amount_cents == amount_cents
        assert refunded.ok and refunded.data.amount_cents == refund_cents
        assert retrieved.ok and retrieved.data.found
        assert retrieved.data.payment is not None
        assert retrieved.data.payment.amount_cents == amount_cents
        assert [item.amount_cents for item in retrieved.data.refunds] == [refund_cents]
    finally:
        _reset_state()
        if prior is None:
            os.environ.pop("PAYMENTS_ENABLE_AUTHORING_TOOLS", None)
        else:
            os.environ["PAYMENTS_ENABLE_AUTHORING_TOOLS"] = prior
