"""Acceptance tests for the complete strict Payments FastMCP surface."""
from __future__ import annotations

import asyncio
from unittest.mock import Mock

import pytest
from pydantic import SecretStr, ValidationError

from factory.mcp_utils.interface import ToolResult
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError
from factory.payments.mcp.contracts.inputs import RegisterProviderInput
from factory.payments.server import create_mcp_server

EXPECTED = {
    "deterministic": {"payments_get_capabilities", "payments_health_check", "payments_describe_config_schema", "payments_get_provider_registry", "payments_get_provider_stats", "payments_list_payments", "payments_get_payment"},
    "operational": {"payments_create_payment", "payments_refund_payment", "payments_process_webhook"},
    "authoring": {"payments_authoring_get_status", "payments_authoring_register_provider", "payments_authoring_unregister_provider", "payments_authoring_update_provider"},
}


def _tools():
    mcp = create_mcp_server()
    return {tool.name: tool for tool in asyncio.run(mcp.list_tools())}


def _tool(name: str):
    return asyncio.run(create_mcp_server().get_tool(name))


def test_exact_catalog_categories_and_typed_envelopes() -> None:
    tools = _tools()
    assert set(tools) == set().union(*EXPECTED.values())
    for category, names in EXPECTED.items():
        for name in names:
            fn = tools[name].fn
            assert getattr(fn, "_mcp_category") == category
            input_model, output_model = getattr(fn, "_mcp_input_model"), getattr(fn, "_mcp_output_model")
            assert input_model.model_config["extra"] == "forbid"
            assert tools[name].return_type == ToolResult[output_model]
            assert tools[name].output_schema is not None


def test_flat_defaults_capabilities_and_safe_config_discovery() -> None:
    tool = _tool("payments_create_payment")
    assert tool.parameters["properties"]["currency"]["default"] == "USD"
    assert tool.parameters["properties"]["metadata"]["default"] is None
    capabilities = _tool("payments_get_capabilities").fn()
    assert capabilities.ok and capabilities.data is not None
    assert capabilities.data.schema_version == "1.0.0"
    assert capabilities.data.running_mode == "stdio"
    assert [(item.type, item.availability) for item in capabilities.data.providers] == [
        ("mock", "available"), ("stripe", "available"), ("paypal", "planned"),
    ]
    config = _tool("payments_describe_config_schema").fn()
    assert config.ok and config.data is not None
    assert config.data.provider_types == ["mock", "stripe", "paypal"]
    assert config.data.payment_statuses and config.data.currencies
    projection = config.data.provider_config
    assert projection.api_key.format == "secret" and projection.api_key.write_only
    assert projection.public_key.format == "secret" and projection.public_key.write_only
    assert projection.options.type == "object"
    assert "sk_" not in str(projection)


@pytest.mark.parametrize("name,kwargs", [
    ("payments_get_capabilities", {"extra": True}),
    ("payments_health_check", {"extra": True}),
    ("payments_describe_config_schema", {"extra": True}),
    ("payments_get_provider_registry", {"extra": True}),
    ("payments_get_provider_stats", {"provider_name": "x", "extra": True}),
    ("payments_list_payments", {"extra": True}),
    ("payments_get_payment", {"payment_id": "x", "extra": True}),
    ("payments_create_payment", {"provider_name": "x", "amount_cents": 1, "extra": True}),
    ("payments_refund_payment", {"payment_id": "x", "extra": True}),
    ("payments_process_webhook", {"provider": "stripe", "payload": {}, "extra": True}),
    ("payments_authoring_get_status", {"extra": True}),
    ("payments_authoring_register_provider", {"name": "x", "provider_type": "mock", "extra": True}),
    ("payments_authoring_unregister_provider", {"name": "x", "extra": True}),
    ("payments_authoring_update_provider", {"name": "x", "extra": True}),
])
def test_every_tool_rejects_unknown_ingress(name: str, kwargs: dict) -> None:
    with pytest.raises(SchemaMigrationError):
        _tool(name).fn(**kwargs)


@pytest.mark.parametrize("field,value", [
    ("metadata", {"nested": {"token": "secret"}}),
    ("metadata", {"nested": {"value": "4242 4242 4242 4242"}}),
    ("options", {"nested": {"card_number": "4242424242424242"}}),
    ("payload", {"data": {"object": {"cvv": "123"}}}),
])
def test_sensitive_nested_json_is_rejected(field: str, value: dict) -> None:
    model = {"metadata": "CreatePaymentInput", "options": "RegisterProviderInput", "payload": "ProcessWebhookInput"}[field]
    from factory.payments.mcp.contracts import inputs
    cls = getattr(inputs, model)
    base = {"metadata": {"provider_name": "x", "amount_cents": 1}, "options": {"name": "x", "provider_type": "mock"}, "payload": {"provider": "stripe"}}[field]
    with pytest.raises(ValidationError):
        cls(**base, **{field: value})


def test_expected_negatives_and_secret_redaction() -> None:
    missing = _tool("payments_get_provider_stats").fn(provider_name="missing")
    assert missing.ok and missing.data.error == "provider_not_found"
    webhook = _tool("payments_process_webhook").fn(provider="other", payload={})
    assert webhook.ok and webhook.data.error == "unknown_provider"
    request = RegisterProviderInput(name="safe", provider_type="mock", api_key=SecretStr("top-secret"))
    assert request.api_key is not None and request.api_key.get_secret_value() == "top-secret"
    assert "top-secret" not in str(_tool("payments_authoring_register_provider").fn(name="safe", provider_type="mock", api_key=SecretStr("top-secret")))


def test_webhook_output_uses_opaque_correlation_id() -> None:
    raw_id = "customer@example.com sk_live_secret 4242 4242 4242 4242 123 Main St"
    result = _tool("payments_process_webhook").fn(provider="stripe", payload={
        "id": raw_id, "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi_1", "customer": "private"}},
    })
    assert result.ok and result.data.processed
    assert result.data.model_dump().keys() == {"processed", "correlation_id", "event_type", "error"}
    assert result.data.correlation_id and result.data.correlation_id.startswith("wh_")
    assert raw_id not in str(result.data)


@pytest.mark.parametrize("payload", [{}, {"type": "unknown.event"}, {"type": ["not", "a", "string"]}])
def test_invalid_webhook_type_does_not_dispatch(payload: dict) -> None:
    handler = __import__("factory.payments.mcp.operational", fromlist=["get_webhook_handler"])
    with pytest.MonkeyPatch.context() as monkeypatch:
        dispatch = Mock()
        webhook_handler = Mock(dispatch=dispatch)
        monkeypatch.setattr(handler, "get_webhook_handler", lambda: webhook_handler)
        result = _tool("payments_process_webhook").fn(provider="stripe", payload=payload)
    assert result.ok and result.data.processed is False
    assert result.data.error == "invalid_event_type"
    dispatch.assert_not_called()
