"""Focused artifact-reference-only email capability tests."""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from factory.integrations.interface import create_server
from factory.integrations.runtime.adapters.fake_email import FakeEmailSender
from factory.integrations.runtime.email_models import SendProtectedEmailRequest
from factory.integrations.runtime.models import RequestResult
from factory.integrations.runtime.runtime import IntegrationsRuntime
from factory.mcp_utils.interface import (
    ProtectedArtifactRef, ProtectedContentDescriptor, reset_envelope, set_envelope,
)


class FakeMaterializer:
    def __init__(self, artifact: ProtectedArtifactRef) -> None:
        self.artifact = artifact
        self.calls = 0

    def materialize(
        self, artifact: ProtectedArtifactRef, principal_id: str, tenant_id: str,
    ) -> dict[str, object]:
        self.calls += 1
        if artifact != self.artifact or principal_id != "owner-a" or tenant_id != "tenant":
            raise ValueError("protected artifact unavailable")
        return {
            "recipients": ["to@example.test"],
            "subject": "private subject", "body": "private body",
        }


def fixture():
    descriptor = ProtectedContentDescriptor(
        classification="business", purpose="email", tenant_id="tenant",
        owner_principal_id="owner-a", artifact_kind="email",
        projection_profile="email-summary",
    )
    artifact = ProtectedArtifactRef(
        artifact_ref="pc_v1_abcdefghijklmnopqrstuv",
        fingerprint="a" * 64, descriptor=descriptor,
    )
    materializer = FakeMaterializer(artifact)
    payload = {
        "connection_ref": "email_conn_123",
        "artifact": artifact.model_dump(mode="json"), "idempotency_key": "send-1",
    }
    runtime = IntegrationsRuntime(materializer=materializer)
    sender = FakeEmailSender()
    runtime.register_email_connection("tenant", "owner-a", payload["connection_ref"], sender)
    return runtime, sender, materializer, payload


def _tool(runtime: IntegrationsRuntime):
    return asyncio.run(create_server(runtime).get_tool("communications.send_email")).fn


def test_wire_rejects_plaintext_and_missing_artifact():
    _, _, _, payload = fixture()
    assert SendProtectedEmailRequest(**payload).artifact.artifact_ref.startswith("pc_v1_")
    with pytest.raises(ValidationError):
        SendProtectedEmailRequest(
            connection_ref=payload["connection_ref"], recipients=["x@example.test"],
            subject="x", body="x", idempotency_key="k",
        )


def test_effect_requires_trusted_owner_tenant_and_artifact_authorization():
    runtime, sender, materializer, payload = fixture()
    tool = _tool(runtime)
    assert tool(**payload).error == "unauthenticated_context"
    token = set_envelope({"principal_id": "owner-a", "tenant_id": "tenant"})
    try:
        result, replay = tool(**payload), tool(**payload)
    finally:
        reset_envelope(token)
    assert result.ok and replay.ok and sender.send_count == 1
    assert materializer.calls == 1
    assert "private body" not in result.model_dump_json()


def test_generic_connector_call_requires_ambient_identity():
    runtime, _, _, _ = fixture()
    runtime.call = MagicMock()  # type: ignore[method-assign]
    tool = asyncio.run(create_server(runtime).get_tool("integrations_call")).fn
    result = tool("connector", "POST", data={"body": "private body"})
    assert result == {
        "success": False, "error": "unauthenticated_context",
        "connector_id": "connector",
    }
    runtime.call.assert_not_called()


def test_generic_connector_call_projects_provider_data():
    runtime, _, _, _ = fixture()
    runtime.call = MagicMock(return_value=RequestResult(
        success=True, status_code=200, latency_ms=12.5, connector_id="connector",
        data={"body": "private body", "provider_token": "secret"},
    ))  # type: ignore[method-assign]
    tool = asyncio.run(create_server(runtime).get_tool("integrations_call")).fn
    token = set_envelope({"principal_id": "owner-a", "tenant_id": "tenant"})
    try:
        result = tool("connector", "POST", data={"body": "private body"})
    finally:
        reset_envelope(token)
    assert result == {
        "success": True, "status_code": 200, "latency_ms": 12.5,
        "connector_id": "connector",
    }
    assert "private body" not in str(result) and "secret" not in str(result)


def test_default_server_fails_closed_without_authentication():
    _, _, _, payload = fixture()
    tool = asyncio.run(create_server().get_tool("communications.send_email")).fn
    assert tool(**payload).error == "unauthenticated_context"


def test_configured_server_composes_fake_protected_email():
    _, _, materializer, payload = fixture()
    payload = {**payload, "idempotency_key": "configured-send-1"}
    tool = asyncio.run(create_server(
        materializer=materializer, fake_email_owner="owner-a",
        fake_email_tenant="tenant", fake_email_connection_ref=payload["connection_ref"],
    ).get_tool("communications.send_email")).fn
    token = set_envelope({"principal_id": "owner-a", "tenant_id": "tenant"})
    try:
        result = tool(**payload)
    finally:
        reset_envelope(token)
    assert result.ok and result.data.status == "sent"


def test_foreign_or_tampered_artifact_fails_before_provider_call():
    runtime, sender, materializer, payload = fixture()
    tool = _tool(runtime)
    token = set_envelope({"principal_id": "other", "tenant_id": "tenant"})
    try:
        denied = tool(**payload)
    finally:
        reset_envelope(token)
    tampered = {
        **payload, "idempotency_key": "tampered-1",
        "artifact": {**payload["artifact"], "fingerprint": "0" * 64},
    }
    token = set_envelope({"principal_id": "owner-a", "tenant_id": "tenant"})
    try:
        invalid = tool(**tampered)
    finally:
        reset_envelope(token)
    assert denied.error == invalid.error == "protected_artifact_unavailable"
    assert sender.send_count == 0 and materializer.calls == 2


def test_provider_exception_is_opaque():
    runtime, _, _, payload = fixture()
    broken = MagicMock()
    broken.send.side_effect = RuntimeError("provider-body-canary@example.test")
    runtime.register_email_connection("tenant", "owner-a", payload["connection_ref"], broken)
    token = set_envelope({"principal_id": "owner-a", "tenant_id": "tenant"})
    try:
        result = _tool(runtime)(**{**payload, "idempotency_key": "provider-failure-1"})
    finally:
        reset_envelope(token)
    assert result.error == "email_provider_failed"
    assert "provider-body-canary" not in result.model_dump_json()


def test_mcp_materializer_rejects_malformed_nested_result_before_provider(monkeypatch):
    from factory.mcp_utils import registry as service_registry

    _, _, _, payload = fixture()
    runtime, sender = IntegrationsRuntime(), FakeEmailSender()
    runtime.register_email_connection("tenant", "owner-a", payload["connection_ref"], sender)
    monkeypatch.setitem(
        service_registry._services, "tool_invoker_for_caller",
        lambda caller: lambda target, **kwargs: {
            "ok": True, "result": {"kind": "tool", "structured_content": {
                "schema_version": "v1", "ok": True,
                "data": {"unexpected": "plaintext"}, "error": None,
                "idempotency_key": None,
            }, "content": [], "meta": {}},
        },
    )
    token = set_envelope({"principal_id": "owner-a", "tenant_id": "tenant"})
    try:
        result = _tool(runtime)(**{**payload, "idempotency_key": "malformed-result-1"})
    finally:
        reset_envelope(token)
    assert result.error == "protected_artifact_unavailable"
    assert sender.send_count == 0
