from __future__ import annotations

import asyncio
import json
import sqlite3
from contextlib import suppress
from pathlib import Path

import pytest
import yaml

from factory.integrations.runtime.adapters.fake_email import FakeEmailSender
from factory.integrations.runtime.runtime import IntegrationsRuntime
from factory.integrations.server import create_tool_catalog as integrations_catalog
from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils import registry as service_registry
from factory.mcp_utils.interface import (
    AccessDecision, AccessPrincipal, ProtectedContentDescriptor, TestKeyProvider,
    reset_envelope, set_envelope,
)
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.storage.runtime.runtime import StorageRuntime
from factory.storage.server import create_tool_catalog as storage_catalog
from factory.workflow.runtime.canonical import canonical_json
from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.runtime import WorkflowRuntime
from factory.workflow.runtime.task_invoker_service import ServiceToolInvoker


def test_workflow_rejects_inline_protected_content_before_persistence():
    for key in ("body", "subject", "recipients", "provider_response", "query"):
        with pytest.raises(ValueError, match="protected inline content is forbidden"):
            canonical_json({"protected_content": True, key: "private-canary"})


def _email_config(tmp_path: Path, artifact: dict) -> Path:
    config = tmp_path / "config"
    (config / "workflows").mkdir(parents=True)
    (config / "settings.yaml").write_text(yaml.safe_dump({
        "storage": {"backend": "sqlite", "sqlite": {"filename": "state.db"}},
        "durable_tasks": {"allowlist": {"send_email": {
            "brick_name": "integrations", "tool_name": "communications.send_email",
        }}},
    }))
    (config / "workflows" / "email.yaml").write_text(yaml.safe_dump({
        "schema_version": "v2", "id": "protected-email", "name": "Protected email",
        "result_projection": {
            "status": {"$ref": "workflow-step:///send/output#/status"},
            "message_id": {"$ref": "workflow-step:///send/output#/message_id"},
        },
        "steps": [{
            "id": "send", "kind": "task", "task_mode": "named_mcp",
            "task_type": "send_email", "idempotency_key_argument": "idempotency_key",
            "task_payload": {"connection_ref": "email_conn_123", "artifact": artifact},
        }],
    }))
    return config


def _sqlite_text(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        return "\n".join(connection.iterdump())


class _AllowController:
    def __init__(self) -> None:
        self.operations = []

    def principal(self) -> AccessPrincipal:
        return AccessPrincipal(subject="owner", client_id="workflow-acceptance")

    def decide(self, _principal, operation) -> AccessDecision:
        self.operations.append(operation)
        return AccessDecision(allowed=True, reason="acceptance policy")


def _public_create(aggregator: MCPAggregator, descriptor: dict, content: dict) -> dict:
    token = set_envelope({"principal_id": "owner", "tenant_id": "tenant"})
    try:
        transport = asyncio.run(aggregator.call_public_brick_tool(
            "storage", "protected_artifact_create",
            {"descriptor": descriptor, "content": content},
        ))
    finally:
        reset_envelope(token)
    assert transport["ok"] is True
    structured = transport["result"]["structured_content"]
    assert structured["ok"] is True
    return structured["data"]["artifact"]


def test_frozen_workflow_uses_hidden_materializer_once_without_copying_content(
    tmp_path, monkeypatch,
):
    canaries = [
        "to+☃@example.test", "private\nsubject", "private unicode body ☃",
        "eyJwcm92aWRlcl9yZXNwb25zZSI6InNlY3JldCJ9",
    ]
    storage_runtime = StorageRuntime({
        "protected_artifact_db_path": str(tmp_path / "protected.db"),
    })
    store = storage_runtime.get_protected_artifact_store(keys=TestKeyProvider())
    materialize_calls = {"count": 0}
    actual_materialize = store.materialize

    def counted_materialize(*args, **kwargs):
        materialize_calls["count"] += 1
        return actual_materialize(*args, **kwargs)

    monkeypatch.setattr(store, "materialize", counted_materialize)
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
    controller = _AllowController()
    monkeypatch.setitem(
        service_registry._services, "tool_invoker_for_caller", native.for_caller,
    )
    monkeypatch.setitem(
        service_registry._services, "mcp_access_controller", controller,
    )
    descriptor = ProtectedContentDescriptor(
        classification="business", purpose="email", tenant_id="tenant",
        owner_principal_id="owner", artifact_kind="email",
        projection_profile="email-summary",
    ).model_dump(mode="json")
    artifact = _public_create(aggregator, descriptor, {
        "recipients": [canaries[0]], "subject": canaries[1],
        "body": f"{canaries[2]} {canaries[3]}",
    })
    executed = [operation for operation in controller.operations if operation.action == "execute"]
    assert [operation.public_name for operation in executed] == [
        "storage_protected_artifact_create",
    ]
    assert "storage_protected_artifact_materialize" not in aggregator.get_brick_tool_names("storage")
    denied = asyncio.run(aggregator.call_public_brick_tool(
        "storage", "protected_artifact_materialize", {"artifact": artifact},
    ))
    assert denied["ok"] is False

    config = _email_config(tmp_path, artifact)
    runtime = WorkflowRuntime.from_config_dir(
        config, tool_invoker=ServiceToolInvoker(native.for_caller("workflow")),
    )
    envelope = Envelope(
        principal_id="owner", tenant_id="tenant", request_id="request-1",
    )
    first = runtime.start_run(
        workflow_name_or_id="protected-email", input={},
        run_key="same-email", envelope=envelope,
    )
    replay = runtime.start_run(
        workflow_name_or_id="protected-email", input={},
        run_key="same-email", envelope=envelope,
    )
    state = runtime.get_run(run_id=first["run_id"], envelope=envelope)
    assert first["status"] == replay["status"] == "succeeded", state
    assert first["run_id"] == replay["run_id"] and sender.send_count == 1
    assert materialize_calls["count"] == 1

    tampered = {**artifact, "fingerprint": "0" * 64}
    rejected = native(
        {"brick_name": "integrations", "tool_name": "communications.send_email"},
        arguments={
            "connection_ref": "email_conn_123", "artifact": tampered,
            "idempotency_key": "tampered-attempt",
        }, idempotency_key="tampered-attempt", envelope={
            "principal_id": "owner", "tenant_id": "tenant",
        },
    )
    assert rejected["result"]["structured_content"]["ok"] is False
    assert sender.send_count == 1

    final = runtime.get_run(run_id=first["run_id"], envelope=envelope)
    assert final["result"]["task_result"]["status"] == "sent"
    attempts = runtime.durable_storage.list_task_attempts(run_id=first["run_id"])
    events = runtime.storage.get_events_since(run_id=first["run_id"], after_event_id=0)
    durable = json.dumps({
        "attempts": attempts,
        "events": [event.model_dump(mode="json") for event in events],
    }, default=str)
    persisted = _sqlite_text(config / "state.db")
    persisted += _sqlite_text(tmp_path / "protected.db") + json.dumps(final, default=str)
    persisted += durable
    for path in (*tmp_path.rglob("*.db-wal"), *tmp_path.rglob("*.db-shm")):
        # -wal/-shm vanish after the glob: SQLite unlinks them on last close.
        with suppress(FileNotFoundError):
            persisted += path.read_text(errors="ignore")
    for canary in canaries:
        assert canary not in persisted
