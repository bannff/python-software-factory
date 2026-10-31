"""Real progressive-gateway acceptance for protected Storage artifacts."""
from __future__ import annotations

import asyncio

from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.interface import (
    AccessDecision, AccessPrincipal, TestKeyProvider, get_service,
    reset_envelope, set_envelope, set_service,
)
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.storage.runtime.runtime import StorageRuntime
from factory.storage.server import create_tool_catalog


class Controller:
    def __init__(self, allowed: bool) -> None:
        self.allowed, self.operations = allowed, []

    def principal(self) -> AccessPrincipal:
        return AccessPrincipal(subject="owner", tenant_id="tenant", client_id="qa")

    def decide(self, _principal, operation) -> AccessDecision:
        self.operations.append(operation)
        return AccessDecision(allowed=self.allowed, reason="qa-policy")


def _system(tmp_path):
    runtime = StorageRuntime({
        "protected_artifact_db_path": str(tmp_path / "protected.db"),
    })
    store = runtime.get_protected_artifact_store(keys=TestKeyProvider())
    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["storage"])
    aggregator._lazy._cache["storage"] = create_tool_catalog(runtime)
    return aggregator, store


def _descriptor() -> dict[str, str]:
    return {
        "classification": "business", "purpose": "email",
        "tenant_id": "tenant", "owner_principal_id": "owner",
        "artifact_kind": "email", "projection_profile": "email-summary",
    }


def _public(aggregator, tool: str, arguments: dict) -> dict:
    token = set_envelope({"principal_id": "owner", "tenant_id": "tenant"})
    try:
        return asyncio.run(aggregator.call_public_brick_tool("storage", tool, arguments))
    finally:
        reset_envelope(token)


def _with_controller(controller, action):
    previous = get_service("mcp_access_controller")
    set_service("mcp_access_controller", controller)
    try:
        return action()
    finally:
        set_service("mcp_access_controller", previous)


def test_real_public_lifecycle_obeys_progressive_allow_policy(tmp_path) -> None:
    aggregator, _ = _system(tmp_path)
    controller = Controller(True)

    def lifecycle():
        created = _public(aggregator, "protected_artifact_create", {
            "descriptor": _descriptor(),
            "content": {"recipients": ["to@example.test"], "subject": "s", "body": "b"},
        })
        artifact = created["result"]["structured_content"]["data"]["artifact"]
        projected = _public(
            aggregator, "protected_artifact_project", {"artifact": artifact},
        )
        tombstoned = _public(
            aggregator, "protected_artifact_tombstone", {"artifact": artifact},
        )
        return created, projected, tombstoned

    results = _with_controller(controller, lifecycle)
    assert all(result["ok"] for result in results)
    assert all(result["result"]["structured_content"]["ok"] for result in results)
    executed = [op.public_name for op in controller.operations if op.action == "execute"]
    assert executed == [
        "storage_protected_artifact_create", "storage_protected_artifact_project",
        "storage_protected_artifact_tombstone",
    ]


def test_real_public_denial_and_forged_authority_have_no_effect(tmp_path) -> None:
    aggregator, _ = _system(tmp_path)
    allow = Controller(True)
    created = _with_controller(allow, lambda: _public(
        aggregator, "protected_artifact_create", {
            "descriptor": _descriptor(),
            "content": {"recipients": ["to@example.test"], "subject": "s", "body": "b"},
        },
    ))
    artifact = created["result"]["structured_content"]["data"]["artifact"]
    deny = Controller(False)
    denied_create = _with_controller(deny, lambda: _public(
        aggregator, "protected_artifact_create", {
            "descriptor": _descriptor(),
            "content": {"recipients": ["blocked@example.test"], "subject": "x", "body": "x"},
        },
    ))
    denied_project = _with_controller(deny, lambda: _public(
        aggregator, "protected_artifact_project", {"artifact": artifact},
    ))
    denied_tombstone = _with_controller(deny, lambda: _public(
        aggregator, "protected_artifact_tombstone", {"artifact": artifact},
    ))
    forged = _with_controller(allow, lambda: _public(
        aggregator, "protected_artifact_tombstone",
        {"artifact": artifact, "envelope": {"principal_id": "attacker"}},
    ))
    still_live = _with_controller(allow, lambda: _public(
        aggregator, "protected_artifact_project", {"artifact": artifact},
    ))
    denied = (denied_create, denied_project, denied_tombstone, forged)
    assert all(result["error"]["message"] == "authorization_denied" for result in denied)
    assert [op.public_name for op in deny.operations if op.action == "execute"] == [
        "storage_protected_artifact_create", "storage_protected_artifact_project",
        "storage_protected_artifact_tombstone",
    ]
    assert still_live["result"]["structured_content"]["ok"] is True


def test_ambient_identity_overrides_forged_explicit_and_wrong_caller_is_denied(
    tmp_path, monkeypatch,
) -> None:
    aggregator, store = _system(tmp_path)
    created = _public(aggregator, "protected_artifact_create", {
        "descriptor": _descriptor(),
        "content": {"recipients": ["to@example.test"], "subject": "s", "body": "b"},
    })
    artifact = created["result"]["structured_content"]["data"]["artifact"]
    calls = {"count": 0}
    actual = store.materialize

    def counted(*args, **kwargs):
        calls["count"] += 1
        return actual(*args, **kwargs)

    monkeypatch.setattr(store, "materialize", counted)
    binding = {key: artifact[key] for key in ("artifact_ref", "fingerprint")}
    token = set_envelope({"principal_id": "owner", "tenant_id": "tenant"})
    try:
        allowed = NativeEnvelopeInvoker(aggregator).for_caller("integrations")(
            {"brick_name": "storage", "tool_name": "protected_artifact_materialize"},
            arguments={"artifact": artifact}, protected_artifact=binding,
            idempotency_key="ambient", envelope={
                "principal_id": "attacker", "tenant_id": "attacker-tenant",
            },
        )
        denied = NativeEnvelopeInvoker(aggregator).for_caller("workflow")(
            {"brick_name": "storage", "tool_name": "protected_artifact_materialize"},
            arguments={"artifact": artifact}, protected_artifact=binding,
            idempotency_key="wrong-caller", envelope={},
        )
    finally:
        reset_envelope(token)
    assert allowed["result"]["structured_content"]["ok"] is True
    assert denied["error"]["type"] == "ServiceOnlyAccessError"
    assert calls["count"] == 1
