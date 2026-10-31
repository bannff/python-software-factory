"""Real MCP-path tamper matrix for protected email artifacts."""
from __future__ import annotations

import json

import pytest

from factory.integrations.runtime.adapters.fake_email import FakeEmailSender
from factory.integrations.runtime.runtime import IntegrationsRuntime
from factory.integrations.server import create_tool_catalog as integrations_catalog
from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils import registry as service_registry
from factory.mcp_utils.interface import ProtectedContentDescriptor, TestKeyProvider
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.storage.runtime.runtime import StorageRuntime
from factory.storage.server import create_tool_catalog as storage_catalog

from .test_integrations_email_named_mcp import _public_create


CASES = (
    ("artifact_ref", "artifact_ref", "different-valid-ref"),
    ("fingerprint", "fingerprint", "0" * 64),
    ("descriptor_owner", "owner_principal_id", "other-owner"),
    ("descriptor_tenant", "tenant_id", "other-tenant"),
    ("descriptor_purpose", "purpose", "review"),
    ("descriptor_kind", "artifact_kind", "document"),
    ("descriptor_projection", "projection_profile", "metadata"),
    ("principal_mismatch", "principal", "other-owner"),
    ("tenant_mismatch", "tenant", "other-tenant"),
)


def _system(tmp_path, monkeypatch):
    storage_runtime = StorageRuntime({
        "protected_artifact_db_path": str(tmp_path / "protected.db"),
    })
    store = storage_runtime.get_protected_artifact_store(keys=TestKeyProvider())
    integrations_runtime = IntegrationsRuntime()
    sender = FakeEmailSender()
    integrations_runtime.register_email_connection(
        "tenant", "owner", "email_conn_123", sender,
    )
    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["storage", "integrations"])
    aggregator._lazy._cache.update({
        "storage": storage_catalog(storage_runtime),
        "integrations": integrations_catalog(integrations_runtime),
    })
    native = NativeEnvelopeInvoker(aggregator)
    monkeypatch.setitem(
        service_registry._services, "tool_invoker_for_caller", native.for_caller,
    )
    descriptor = ProtectedContentDescriptor(
        classification="business", purpose="email", tenant_id="tenant",
        owner_principal_id="owner", artifact_kind="email",
        projection_profile="email-summary",
    ).model_dump(mode="json")
    canary = "private-real-path-canary@example.test"
    artifact = _public_create(aggregator, descriptor, {
        "recipients": [canary], "subject": "private subject", "body": canary,
    })
    return aggregator, native, store, sender, artifact, canary


def _mutate(artifact: dict, slot: str, value: str) -> dict:
    if slot == "artifact_ref":
        suffix = "a" if artifact[slot][-1] != "a" else "b"
        return {**artifact, slot: artifact[slot][:-1] + suffix}
    if slot == "fingerprint":
        return {**artifact, slot: value}
    if slot in {"principal", "tenant"}:
        return artifact
    return {**artifact, "descriptor": {**artifact["descriptor"], slot: value}}


@pytest.mark.parametrize("label,slot,value", CASES, ids=[case[0] for case in CASES])
def test_tamper_and_identity_matrix_fails_before_provider_effect(
    tmp_path, monkeypatch, label: str, slot: str, value: str,
) -> None:
    _, native, store, sender, artifact, canary = _system(tmp_path, monkeypatch)
    calls = {"count": 0}
    actual = store.materialize

    def counted(*args, **kwargs):
        calls["count"] += 1
        return actual(*args, **kwargs)

    monkeypatch.setattr(store, "materialize", counted)
    candidate = _mutate(artifact, slot, value)
    principal = value if slot == "principal" else "owner"
    tenant = value if slot == "tenant" else "tenant"
    transport = native(
        {"brick_name": "integrations", "tool_name": "communications.send_email"},
        arguments={
            "connection_ref": "email_conn_123", "artifact": candidate,
            "idempotency_key": f"tamper-{label}",
        }, idempotency_key=f"tamper-{label}",
        envelope={"principal_id": principal, "tenant_id": tenant},
    )
    assert transport["ok"] is True
    structured = transport["result"]["structured_content"]
    assert structured["ok"] is False
    assert structured["error"] == "protected_artifact_unavailable"
    assert sender.send_count == 0
    assert calls["count"] <= 1
    assert canary not in json.dumps(transport, ensure_ascii=False)
