"""Protected-artifact public and service-only MCP boundary tests."""
from __future__ import annotations

import asyncio

import pytest

from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.interface import (
    ServiceOnlyAccessError, TestKeyProvider, reset_envelope, set_envelope,
)
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.storage.runtime.runtime import StorageRuntime
from factory.storage.server import create_tool_catalog


def _descriptor() -> dict[str, object]:
    return {
        "classification": "business", "purpose": "email",
        "tenant_id": "tenant", "owner_principal_id": "owner",
        "artifact_kind": "email", "projection_profile": "email-summary",
    }


def _fixture(tmp_path):
    runtime = StorageRuntime({
        "protected_artifact_db_path": str(tmp_path / "protected.db"),
    })
    runtime.get_protected_artifact_store(keys=TestKeyProvider())
    catalog = create_tool_catalog(runtime)
    return catalog


def _public(catalog, name: str, arguments: dict, *, owner: str = "owner"):
    tool = asyncio.run(catalog.get_tool(name))
    token = set_envelope({"principal_id": owner, "tenant_id": "tenant"})
    try:
        return tool.fn(**arguments)
    finally:
        reset_envelope(token)


def test_public_create_project_and_tombstone_are_typed_and_opaque(tmp_path) -> None:
    catalog = _fixture(tmp_path)
    created = _public(catalog, "protected_artifact_create", {
        "descriptor": _descriptor(),
        "content": {
            "recipients": ["canary@example.test"],
            "subject": "private subject", "body": "private body",
        },
    })
    assert created.ok and created.data.status == "created"
    artifact = created.data.artifact.model_dump(mode="json")
    projected = _public(catalog, "protected_artifact_project", {"artifact": artifact})
    assert projected.ok and projected.data.projection.values["recipient_count"] == 1
    denied = _public(
        catalog, "protected_artifact_project", {"artifact": artifact}, owner="other",
    )
    assert denied.ok is False and denied.error == "protected_artifact_unavailable"
    tombstoned = _public(catalog, "protected_artifact_tombstone", {"artifact": artifact})
    assert tombstoned.ok and tombstoned.data.tombstoned is True
    unavailable = _public(catalog, "protected_artifact_project", {"artifact": artifact})
    assert unavailable.ok is False and unavailable.error == "protected_artifact_unavailable"


def test_materialize_is_hidden_denied_publicly_and_requires_exact_binding(tmp_path) -> None:
    catalog = _fixture(tmp_path)
    created = _public(catalog, "protected_artifact_create", {
        "descriptor": _descriptor(),
        "content": {
            "recipients": ["to@example.test"], "subject": "s", "body": "b",
        },
    })
    artifact = created.data.artifact.model_dump(mode="json")
    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["storage"])
    aggregator._lazy._cache["storage"] = catalog
    assert "storage_protected_artifact_materialize" not in aggregator.get_brick_tool_names("storage")
    direct = asyncio.run(catalog.get_tool("protected_artifact_materialize"))
    with pytest.raises(ServiceOnlyAccessError):
        direct.fn(artifact=artifact)
    public = asyncio.run(aggregator.call_public_brick_tool(
        "storage", "protected_artifact_materialize", {"artifact": artifact},
    ))
    assert public["ok"] is False
    binding = {key: artifact[key] for key in ("artifact_ref", "fingerprint")}
    result = NativeEnvelopeInvoker(aggregator).for_caller("integrations")(
        {"brick_name": "storage", "tool_name": "protected_artifact_materialize"},
        arguments={"artifact": artifact}, protected_artifact=binding,
        idempotency_key="materialize-once",
        envelope={"principal_id": "owner", "tenant_id": "tenant"},
    )
    assert result["ok"] is True
    structured = result["result"]["structured_content"]
    assert structured["ok"] is True and structured["data"]["content"]["body"] == "b"
    tampered = NativeEnvelopeInvoker(aggregator).for_caller("integrations")(
        {"brick_name": "storage", "tool_name": "protected_artifact_materialize"},
        arguments={"artifact": {**artifact, "fingerprint": "f" * 64}},
        protected_artifact=binding, idempotency_key="tampered",
        envelope={"principal_id": "owner", "tenant_id": "tenant"},
    )
    assert tampered["error"]["type"] == "ServiceOnlyAccessError"
