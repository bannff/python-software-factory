"""Exact service-only Workflow boundary tests for Migration apply execution."""
from __future__ import annotations

import asyncio

import pytest

from factory.mcp_utils.interface import (
    ExecutionBinding, ServiceOnlyAccessError, acquire_service_entry,
    begin_service_invocation, end_service_invocation,
    mint_internal_invocation_claims, reset_envelope,
    reset_internal_invocation_claims, service_binding, service_callers,
    set_envelope, set_internal_invocation_claims,
)
from factory.migration.mcp.execution import register
from factory.migration.runtime.adapters.receipt_store_sql import SqlReceiptStore
from factory.migration.runtime.preview import PreviewRuntime
from factory.migration.runtime.receipt_models import PlanIdentity
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.storage.interface import StorageRuntime

_TOOL = "migration_apply_execution"


def _values() -> dict:
    return {
        "request": {
            "tenant_id": "tenant", "owner_id": "owner",
            "source_adapter": "kirocrew-v1", "source_fingerprint": "a" * 64,
            "plan_digest": "sha256:" + "b" * 64,
            "kinds": ["memory"], "page_size": 10,
        },
        "provider_request_digest": "c" * 64,
        "workflow_run_id": "run-1", "attempt_id": "attempt-1", "revision": 1,
        "engine_id": "migration_import", "registration_digest": "d" * 64,
        "request_digest": "e" * 64,
    }


def _runtime(tmp_path) -> PreviewRuntime:
    store = SqlReceiptStore(StorageRuntime().get_sql_store(
        "sqlite", db_path=str(tmp_path / "apply-mcp.db")))
    request = _values()["request"]
    store.bind_plan(PlanIdentity(
        tenant_id=request["tenant_id"], owner_id=request["owner_id"],
        adapter=request["source_adapter"],
        source_fingerprint=request["source_fingerprint"],
        plan_digest=request["plan_digest"], kinds=("memory",),
    ))
    return PreviewRuntime(None, store)


async def _tool(runtime):
    catalog = ToolCatalog("migration")
    register(catalog, lambda: runtime)
    return await catalog.get_tool(_TOOL)


def _dispatch(tool, values: dict, *, owner="owner"):
    binding = ExecutionBinding(**{
        key: values[key] for key in (
            "workflow_run_id", "attempt_id", "revision", "engine_id",
            "registration_digest", "request_digest", "provider_request_digest",
        )
    })

    async def run():
        claims = mint_internal_invocation_claims(
            caller="workflow", audience="migration", target_tool=_TOOL,
            binding=binding, target=tool)
        token = set_internal_invocation_claims(claims)
        envelope = set_envelope({
            "tenant_id": "tenant", "principal_id": owner,
            "session_id": "session", "thread_id": "thread", "run_id": "run-1",
        })
        state = None
        try:
            state = begin_service_invocation(
                tool, audience="migration", target_tool=_TOOL, arguments=values)
            entry = acquire_service_entry(tool.fn)
            return tool.fn(**values, _service_entry_authorization=entry)
        finally:
            end_service_invocation(state)
            reset_envelope(envelope)
            reset_internal_invocation_claims(token)

    return asyncio.run(run())


def test_apply_tool_requires_exact_workflow_execution_binding(tmp_path, monkeypatch) -> None:
    tool = asyncio.run(_tool(_runtime(tmp_path)))
    assert service_callers(tool) == frozenset({"workflow"})
    assert service_binding(tool) == "execution"
    monkeypatch.setattr(
        "factory.migration.mcp.execution.get_service",
        lambda name: (lambda _caller: lambda *_a, **_k: {})
        if name == "tool_invoker_for_caller" else None,
    )
    result = _dispatch(tool, _values())
    assert result.ok and result.data.status == "completed"


def test_unauthorized_precedes_invalid_request(tmp_path) -> None:
    tool = asyncio.run(_tool(_runtime(tmp_path)))
    with pytest.raises(ServiceOnlyAccessError):
        tool.fn(request={"invalid": True})


def test_ambient_owner_mismatch_fails_safely(tmp_path, monkeypatch) -> None:
    tool = asyncio.run(_tool(_runtime(tmp_path)))
    monkeypatch.setattr(
        "factory.migration.mcp.execution.get_service", lambda _name: None)
    result = _dispatch(tool, _values(), owner="other")
    assert result.ok is False and result.error == "migration_apply_unavailable"
