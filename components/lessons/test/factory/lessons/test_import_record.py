"""Protected Migration→Lessons import boundary and semantics tests."""
from __future__ import annotations

import asyncio

import pytest

from factory.lessons.runtime.adapters.sql import SQLLessonStore
from factory.lessons.runtime.identity import import_target_digest
from factory.lessons.runtime.lifecycle import LessonLifecycle
from factory.lessons.runtime.runtime import LessonsRuntime
from factory.lessons.server import create_mcp_server
from factory.mcp_utils.interface import (
    MigrationImportBinding, ServiceOnlyAccessError, acquire_service_entry,
    begin_service_invocation, end_service_invocation,
    mint_internal_invocation_claims, reset_envelope,
    reset_internal_invocation_claims, set_envelope,
    set_internal_invocation_claims,
)
from factory.storage.interface import StorageRuntime

_TOOL = "lessons_import_record"
_ADAPTER = "kirocrew-v1"
_RECORD = "c" * 64
_FINGERPRINT = "a" * 64
_PLAN = "b" * 64


def _runtime(tmp_path) -> LessonsRuntime:
    sql = StorageRuntime().get_sql_store("sqlite", db_path=str(tmp_path / "lessons.db"))
    return LessonsRuntime(LessonLifecycle(SQLLessonStore(sql)))


def _values(**changes) -> dict:
    tenant = changes.pop("tenant_id", "tenant")
    owner = changes.pop("owner_id", "owner")
    rule = changes.pop("rule", "Always cite the exact source")
    negative = changes.pop("negative", None)
    category = changes.pop("category", "knowledge")
    repo_scope = changes.pop("repo_scope", "")
    evidence = tuple(changes.pop("evidence", ()))
    record_id = changes.pop("source_record_id", _RECORD)
    adapter = changes.pop("source_adapter", _ADAPTER)
    digest = changes.pop("target_digest", None)
    if digest is None:
        digest = import_target_digest(
            tenant, owner, adapter, record_id, rule, negative, category,
            repo_scope, evidence,
        )
    values = {
        "tenant_id": tenant, "owner_id": owner, "source_adapter": adapter,
        "source_fingerprint": _FINGERPRINT, "plan_digest": _PLAN,
        "kind": "lessons", "source_record_id": record_id,
        "target_digest": digest, "rule": rule, "negative": negative,
        "category": category, "repo_scope": repo_scope, "evidence": evidence,
    }
    values.update(changes)
    return values


async def _import(mcp, values: dict):
    """Drive the service-only boundary exactly as the native invoker does."""
    tool = await mcp.get_tool(_TOOL)
    binding = MigrationImportBinding(**{
        key: values[key] for key in (
            "tenant_id", "owner_id", "source_adapter", "source_fingerprint",
            "plan_digest", "kind", "source_record_id", "target_digest",
        )
    })
    token = set_internal_invocation_claims(mint_internal_invocation_claims(
        caller="migration", audience="lessons", target_tool=_TOOL,
        binding=binding, target=tool,
    ))
    envelope_token = set_envelope({
        "tenant_id": values["tenant_id"], "principal_id": values["owner_id"],
        "session_id": "migration-session", "thread_id": "migration-thread",
    })
    state = None
    try:
        state = begin_service_invocation(
            tool, audience="lessons", target_tool=_TOOL, arguments=values,
        )
        invoke_args = {**values, "_service_entry_authorization": acquire_service_entry(tool.fn)}
        return await mcp.call_tool(_TOOL, invoke_args)
    finally:
        end_service_invocation(state)
        reset_envelope(envelope_token)
        reset_internal_invocation_claims(token)


def _data(result):
    return result.structured_content["data"]


def test_unauthorized_call_is_refused_before_dto_and_effects(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    mcp = create_mcp_server(runtime)
    # Missing/invalid content would fail the DTO — but the boundary must reject
    # first, so nothing is validated and nothing is written.
    values = {"tenant_id": "tenant", "owner_id": "owner", "kind": "nope"}
    with pytest.raises(ServiceOnlyAccessError):
        asyncio.run(mcp.call_tool(_TOOL, values))
    assert runtime.lifecycle.list("tenant", "owner") == []


def test_exact_binding_is_required_at_the_boundary(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    mcp = create_mcp_server(runtime)
    values = _values()

    async def drive() -> None:
        tool = await mcp.get_tool(_TOOL)
        # A binding whose fields do not match the call arguments is rejected.
        binding = MigrationImportBinding(**{
            key: values[key] for key in (
                "tenant_id", "owner_id", "source_adapter", "source_fingerprint",
                "plan_digest", "kind", "source_record_id", "target_digest",
            )
        })
        token = set_internal_invocation_claims(mint_internal_invocation_claims(
            caller="migration", audience="lessons", target_tool=_TOOL,
            binding=binding, target=tool,
        ))
        try:
            with pytest.raises(ServiceOnlyAccessError):
                begin_service_invocation(
                    tool, audience="lessons", target_tool=_TOOL,
                    arguments={**values, "source_record_id": "d" * 64},
                )
        finally:
            reset_internal_invocation_claims(token)

    asyncio.run(drive())
    assert runtime.lifecycle.list("tenant", "owner") == []


def test_wrong_caller_is_refused(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    mcp = create_mcp_server(runtime)
    values = _values()

    async def drive() -> None:
        tool = await mcp.get_tool(_TOOL)
        binding = MigrationImportBinding(**{
            key: values[key] for key in (
                "tenant_id", "owner_id", "source_adapter", "source_fingerprint",
                "plan_digest", "kind", "source_record_id", "target_digest",
            )
        })
        token = set_internal_invocation_claims(mint_internal_invocation_claims(
            caller="agent", audience="lessons", target_tool=_TOOL,
            binding=binding, target=tool,
        ))
        try:
            with pytest.raises(ServiceOnlyAccessError):
                begin_service_invocation(
                    tool, audience="lessons", target_tool=_TOOL, arguments=values,
                )
        finally:
            reset_internal_invocation_claims(token)

    asyncio.run(drive())


def test_forged_target_digest_is_refused_before_write(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    mcp = create_mcp_server(runtime)
    values = _values(target_digest="e" * 64)
    result = asyncio.run(_import(mcp, values))
    assert result.structured_content["ok"] is False
    assert runtime.lifecycle.list("tenant", "owner") == []


