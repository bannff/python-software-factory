"""wd87r: the secret/token canary must not reach logging or returned envelopes.

Drives the full MCP egress path (success + bad-digest + wrong-caller) with a
root-level DEBUG log capture and asserts neither the durable-secret canary nor
the broker's access-token prefix appears in any log record or returned payload.

Note on the other sinks named in the acceptance list: the egress path emits no
events, and OTel tool spans record only brick.name/tool.name (never payloads),
so logging + returned envelopes are the sinks that could actually carry a
secret in this in-process harness.
"""
from __future__ import annotations

import logging

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

CANARY = "refresh-CANARY-sinks-777888999aaabbbcccddd"


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
    broker = CredentialBroker(ServiceSecretStore(), {"microsoft": FakeProvider()})
    monkeypatch.setitem(service_registry._services, "credential_broker", broker)
    token = set_envelope({"principal_id": "o1", "tenant_id": "t1"})
    try:
        broker.enroll(SlotCoordinate("t1", "o1", "microsoft", "c1", "refresh_token"),
                      {"refresh_token": CANARY})
    finally:
        reset_envelope(token)
    return native


def _egress(native, caller, *, digest=None):
    payload = {"subject": "s", "body": "b", "to": "t@x.z"}
    rd = digest or request_digest("microsoft", "send_mail", "c1", payload)
    request = {"provider_id": "microsoft", "route_id": "send_mail",
               "connection_ref": "c1", "payload": payload, "request_digest": rd}
    binding = {"provider_id": "microsoft", "route_id": "send_mail",
               "connection_ref": "c1", "request_digest": rd}
    return native.for_caller(caller)(
        {"brick_name": "auth", "tool_name": "auth.credentialed_egress"},
        arguments={"request": request}, idempotency_key="egress-1",
        envelope={"principal_id": "o1", "tenant_id": "t1"},
        credential_egress=binding)


def test_canary_and_access_token_absent_from_logs_and_envelopes(rig, caplog):
    native = rig
    with caplog.at_level(logging.DEBUG):
        ok = _egress(native, "integrations")
        bad = _egress(native, "integrations",
                      digest=request_digest("microsoft", "send_mail", "c1", {}))
        wrong = _egress(native, "workflow")
    # the successful call really ran end-to-end
    assert ok["result"]["structured_content"]["data"]["status"] == "ok"
    assert bad["result"]["structured_content"]["ok"] is False
    assert wrong["error"]["type"] == "ServiceOnlyAccessError"
    # neither the durable secret nor the fabricated access token leaked to logs
    logged = caplog.text
    assert CANARY not in logged
    assert "fat_" not in logged
    # nor to any returned envelope
    for result in (ok, bad, wrong):
        blob = str(result)
        assert CANARY not in blob and "fat_" not in blob
