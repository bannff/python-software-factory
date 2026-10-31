"""Black-box acceptance: MCPAggregator -> caller-bound NativeEnvelopeInvoker ->
hidden auth.credentialed_egress -> broker -> hidden storage.credential_slot_read.

Proves the identical path for the Microsoft-delegated and Adobe
client-credentials fakes, and that the egress tool is hidden, integrations-only,
rejects field injection / digest tampering, and never leaks a secret or token.
"""
from __future__ import annotations

import pytest

from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils import registry as service_registry
from factory.mcp_utils.interface import TestKeyProvider, reset_envelope, set_envelope
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.auth.server import create_tool_catalog as auth_catalog
from factory.auth.runtime.credential_broker import CredentialBroker
from factory.auth.runtime.adapters.fake_providers import FakeProvider
from factory.auth.runtime.adapters.secret_store_service import ServiceSecretStore
from factory.auth.runtime.egress_models import SlotCoordinate, request_digest
from factory.storage.runtime.runtime import StorageRuntime
from factory.storage.server import create_tool_catalog as storage_catalog

MS_CANARY = "refresh-CANARY-ms-1234567890abcdef"
ADOBE_CANARY = "client-CANARY-adobe-abcdef1234567890"


@pytest.fixture
def rig(tmp_path, monkeypatch):
    runtime = StorageRuntime({"credential_slot_db_path": str(tmp_path / "slots.db")})
    runtime.get_credential_slot_store(keys=TestKeyProvider())
    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["auth", "storage"])
    aggregator._lazy._cache["auth"] = auth_catalog()
    aggregator._lazy._cache["storage"] = storage_catalog(runtime)
    native = NativeEnvelopeInvoker(aggregator)
    monkeypatch.setitem(service_registry._services, "tool_invoker_for_caller", native.for_caller)
    providers = {"microsoft": FakeProvider(), "adobe": FakeProvider()}
    broker = CredentialBroker(ServiceSecretStore(), providers)
    monkeypatch.setitem(service_registry._services, "credential_broker", broker)
    return aggregator, native, broker, providers


def _egress(native, caller, provider, route, connection, payload, *, digest=None):
    rd = digest or request_digest(provider, route, connection, payload)
    request = {"provider_id": provider, "route_id": route,
               "connection_ref": connection, "payload": payload, "request_digest": rd}
    binding = {"provider_id": provider, "route_id": route,
               "connection_ref": connection, "request_digest": rd}
    return native.for_caller(caller)(
        {"brick_name": "auth", "tool_name": "auth.credentialed_egress"},
        arguments={"request": request}, idempotency_key="egress-1",
        envelope={"principal_id": "o1", "tenant_id": "t1"},
        credential_egress=binding,
    )


def test_microsoft_delegated_end_to_end(rig):
    _, native, broker, _ = rig
    token = set_envelope({"principal_id": "o1", "tenant_id": "t1"})
    try:
        assert broker.enroll(
            SlotCoordinate("t1", "o1", "microsoft", "c1", "refresh_token"),
            {"refresh_token": MS_CANARY})
    finally:
        reset_envelope(token)
    result = _egress(native, "integrations", "microsoft", "send_mail", "c1",
                     {"subject": "hi", "body": "b", "to": "x@y.z"})
    assert result["ok"] is True
    structured = result["result"]["structured_content"]
    assert structured["ok"] is True and structured["data"]["status"] == "ok"
    blob = str(result)
    assert MS_CANARY not in blob and "fat_" not in blob  # no secret, no access token


def test_adobe_client_credentials_end_to_end(rig):
    _, native, broker, _ = rig
    token = set_envelope({"principal_id": "o1", "tenant_id": "t1"})
    try:
        assert broker.enroll(
            SlotCoordinate("t1", "o1", "adobe", "cA", "client_secret"),
            {"client_secret": ADOBE_CANARY})
    finally:
        reset_envelope(token)
    result = _egress(native, "integrations", "adobe", "indesign_datamerge", "cA",
                     {"template_ref": "tpl", "data_ref": "csv"})
    structured = result["result"]["structured_content"]
    assert structured["ok"] is True and structured["data"]["result"]["provider_id"] == "adobe"
    assert ADOBE_CANARY not in str(result)


def test_wrong_caller_is_denied(rig):
    _, native, broker, _ = rig
    token = set_envelope({"principal_id": "o1", "tenant_id": "t1"})
    try:
        broker.enroll(SlotCoordinate("t1", "o1", "microsoft", "c1", "refresh_token"),
                      {"refresh_token": MS_CANARY})
    finally:
        reset_envelope(token)
    denied = _egress(native, "workflow", "microsoft", "send_mail", "c1",
                     {"subject": "s", "body": "b", "to": "t@x.z"})
    assert denied["error"]["type"] == "ServiceOnlyAccessError"


def test_public_call_without_binding_is_denied(rig):
    aggregator, _, _, _ = rig
    import asyncio
    public = asyncio.run(aggregator.call_public_brick_tool(
        "auth", "auth.credentialed_egress",
        {"request": {"provider_id": "microsoft", "route_id": "send_mail",
                     "connection_ref": "c1", "payload": {}, "request_digest": "0" * 64}}))
    assert public["ok"] is False


def test_field_injection_rejected(rig):
    _, native, broker, _ = rig
    token = set_envelope({"principal_id": "o1", "tenant_id": "t1"})
    try:
        broker.enroll(SlotCoordinate("t1", "o1", "microsoft", "c1", "refresh_token"),
                      {"refresh_token": MS_CANARY})
    finally:
        reset_envelope(token)
    # extra field not allowed by the route; digest is honestly computed over it
    result = _egress(native, "integrations", "microsoft", "send_mail", "c1",
                     {"subject": "s", "body": "b", "to": "t@x.z", "cc": "evil@x.z"})
    structured = result["result"]["structured_content"]
    assert structured["ok"] is False and structured["error"] == "credential_egress_denied"


def test_digest_tamper_rejected(rig):
    _, native, broker, _ = rig
    token = set_envelope({"principal_id": "o1", "tenant_id": "t1"})
    try:
        broker.enroll(SlotCoordinate("t1", "o1", "microsoft", "c1", "refresh_token"),
                      {"refresh_token": MS_CANARY})
    finally:
        reset_envelope(token)
    # digest matches an EMPTY payload but the real payload differs -> recompute mismatch
    stale = request_digest("microsoft", "send_mail", "c1", {})
    result = _egress(native, "integrations", "microsoft", "send_mail", "c1",
                     {"subject": "s", "body": "b", "to": "t@x.z"}, digest=stale)
    # binding mismatch (stale digest) trips the service boundary before the handler
    assert result.get("error", {}).get("type") == "ServiceOnlyAccessError" or \
        result["result"]["structured_content"]["ok"] is False


def test_egress_tool_hidden_from_discovery(rig):
    aggregator, _, _, _ = rig
    assert "auth_credentialed_egress" not in aggregator.get_brick_tool_names("auth")
    names = aggregator.get_brick_tool_names("storage")
    assert not any("credential_slot" in n for n in names)
