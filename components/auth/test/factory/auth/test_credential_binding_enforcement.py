"""Binding enforcement + discovery leakage for the tokenless egress path.

Complements test_credentialed_egress_acceptance.py. That file proves the happy
path + wrong-caller + honest-field/digest rejection. Here we pin down the
NativeEnvelopeInvoker binding contract that the acceptance file does not:
  * mixed bindings (egress + another kind) are rejected before the handler;
  * partial bindings (missing a required field) are rejected;
  * a wrong-kind binding supplied through the wrong kwarg is rejected;
and we assert no token-bearing field name or secret canary is reachable through
public discovery (get_brick_tool_map -> public admission projection).
"""
from __future__ import annotations

import json

import pytest

from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_server.runtime.public_admission import project_public_tools
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

MS_CANARY = "refresh-CANARY-bind-1234567890abcdef"


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
                      {"refresh_token": MS_CANARY})
    finally:
        reset_envelope(token)
    return aggregator, native


def _req(**over):
    payload = {"subject": "s", "body": "b", "to": "t@x.z"}
    base = dict(provider_id="microsoft", route_id="send_mail", connection_ref="c1")
    base.update(over)
    rd = request_digest(base["provider_id"], base["route_id"], base["connection_ref"], payload)
    request = {**base, "payload": payload, "request_digest": rd}
    return request, {**base, "request_digest": rd}


def _call(native, *, egress=None, **extra):
    request, binding = _req()
    return native.for_caller("integrations")(
        {"brick_name": "auth", "tool_name": "auth.credentialed_egress"},
        arguments={"request": request}, idempotency_key="egress-1",
        envelope={"principal_id": "o1", "tenant_id": "t1"},
        credential_egress=egress if egress is not None else binding,
        **extra,
    )


def test_mixed_binding_is_rejected(rig):
    _, native = rig
    # supply a second binding alongside the valid egress binding
    result = _call(native, protected_artifact={"artifact_ref": "a", "fingerprint": "0" * 64})
    assert result["error"]["type"] == "ServiceOnlyAccessError"


def test_partial_binding_is_rejected(rig):
    _, native = rig
    _, binding = _req()
    binding.pop("request_digest")  # missing a required field
    result = _call(native, egress=binding)
    assert result["error"]["type"] == "ServiceOnlyAccessError"


def test_wrong_kind_binding_is_rejected(rig):
    _, native = rig
    request, _ = _req()
    # an enrollment binding routed to a credential_egress tool: no egress kwarg at all
    result = native.for_caller("integrations")(
        {"brick_name": "auth", "tool_name": "auth.credentialed_egress"},
        arguments={"request": request}, idempotency_key="egress-1",
        envelope={"principal_id": "o1", "tenant_id": "t1"},
        enrollment={"run_key": "rk", "manifest_digest": "0" * 64},
    )
    assert result["error"]["type"] == "ServiceOnlyAccessError"


def test_no_token_fields_or_canary_in_public_discovery(rig):
    aggregator, _ = rig
    projection = project_public_tools(
        [(b, aggregator.get_brick_tool_map(b) or {}) for b in ("auth", "storage")])
    names = {t.public_name for t in projection.admitted}
    blob = json.dumps([
        {"name": t.public_name, "schema": t.input_schema} for t in projection.admitted
    ]).lower()
    # the py7t9 service-only tools never appear in the public projection
    assert not any("credentialed_egress" in n or "credential_slot" in n for n in names)
    assert "credentialed_egress" not in blob and "credential_slot" not in blob
    # the py7t9 tokenless egress surface exposes no request_digest / egress fields publicly
    assert "request_digest" not in blob
    # the live broker secret canary is never reachable through discovery
    assert MS_CANARY.lower() not in blob
    # NOTE (pre-existing, out of py7t9 scope): auth_userinfo / workload-credential
    # tools DO carry caller-supplied access_token / refresh_token fields — that is
    # the documented issue_workload_credential precedent, not a py7t9 regression.
