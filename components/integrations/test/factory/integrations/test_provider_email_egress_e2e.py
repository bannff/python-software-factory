"""qk44z: vendor-neutral email capability -> tokenless egress rail, end-to-end.

Full path: agent calls public communications.provider_email_send ->
EgressEmailAdapter (caller=integrations) -> hidden auth.credentialed_egress ->
broker -> hidden storage.credential_slot_read -> Microsoft fake. Proves the
capability composes with the merged py7t9 rail and never leaks a secret/token.
"""
from __future__ import annotations

import asyncio

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
from factory.auth.runtime.egress_models import SlotCoordinate
from factory.integrations.server import create_tool_catalog as integrations_catalog
from factory.storage.runtime.runtime import StorageRuntime
from factory.storage.server import create_tool_catalog as storage_catalog

CANARY = "refresh-CANARY-qk44z-eeff00112233"


@pytest.fixture
def rig(tmp_path, monkeypatch):
    runtime = StorageRuntime({"credential_slot_db_path": str(tmp_path / "slots.db")})
    runtime.get_credential_slot_store(keys=TestKeyProvider())
    agg = MCPAggregator(ToolCatalog("root"))
    agg.set_available_bricks(["auth", "storage", "integrations"])
    agg._lazy._cache["auth"] = auth_catalog()
    agg._lazy._cache["storage"] = storage_catalog(runtime)
    integrations = integrations_catalog()
    agg._lazy._cache["integrations"] = integrations
    native = NativeEnvelopeInvoker(agg)
    monkeypatch.setitem(service_registry._services, "tool_invoker_for_caller", native.for_caller)
    broker = CredentialBroker(ServiceSecretStore(), {"microsoft": FakeProvider()})
    monkeypatch.setitem(service_registry._services, "credential_broker", broker)
    token = set_envelope({"principal_id": "o1", "tenant_id": "t1"})
    try:
        broker.enroll(SlotCoordinate("t1", "o1", "microsoft", "c1", "refresh_token"),
                      {"refresh_token": CANARY})
    finally:
        reset_envelope(token)
    return agg, integrations


def _tool(catalog, name):
    return asyncio.run(catalog.get_tool(name))


def _send(catalog, **kwargs):
    fn = _tool(catalog, "communications.provider_email_send").fn
    token = set_envelope({"principal_id": "o1", "tenant_id": "t1"})
    try:
        return fn(**kwargs)
    finally:
        reset_envelope(token)


def test_send_email_end_to_end_through_egress_rail(rig):
    _, integrations = rig
    result = _send(integrations, provider_id="microsoft", connection_ref="c1",
                   subject="Hello", body="from the assistant", to="jane@example.test")
    assert result.ok and result.data.status == "ok"
    assert result.data.result["provider_id"] == "microsoft"
    # business-content field names are redacted from results by sanitize_protected
    # (a real provider returns a message id here, not the echoed subject/body)
    assert result.data.result["echo"]["subject"] == "[protected]"
    blob = result.model_dump_json()
    assert CANARY not in blob and "fat_" not in blob  # no secret, no access token


def test_list_messages_end_to_end(rig):
    _, integrations = rig
    fn = _tool(integrations, "communications.provider_email_list").fn
    token = set_envelope({"principal_id": "o1", "tenant_id": "t1"})
    try:
        result = fn(provider_id="microsoft", connection_ref="c1", top=5, query="")
    finally:
        reset_envelope(token)
    assert result.ok and result.data.status == "ok"
    assert result.data.result["route_id"] == "list_messages"


def test_unknown_provider_is_denied(rig):
    _, integrations = rig
    result = _send(integrations, provider_id="nope", connection_ref="c1",
                   subject="s", body="b", to="x@y.z")
    assert result.ok is False and result.error == "email_egress_denied"


def test_unauthenticated_context_rejected(rig):
    _, integrations = rig
    # no envelope set -> no principal/tenant
    result = _tool(integrations, "communications.provider_email_send").fn(
        provider_id="microsoft", connection_ref="c1", subject="s", body="b", to="x@y.z")
    assert result.ok is False and result.error == "unauthenticated_context"


def test_egress_tool_stays_hidden_from_public_discovery(rig):
    agg, _ = rig
    assert "auth_credentialed_egress" not in agg.get_brick_tool_names("auth")
    names = agg.get_brick_tool_names("integrations")
    assert any("provider_email_send" in n for n in names)  # the public capability IS visible
