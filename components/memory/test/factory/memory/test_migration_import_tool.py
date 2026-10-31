"""Protected Memory import tool (M7 slice 2): authz precedence, exact binding,
digest verification, owner isolation, replay, subtype mapping, tags, strict
input."""
from __future__ import annotations

import asyncio

import pytest

from factory.mcp_utils.interface import (
    MigrationImportBinding, ServiceOnlyAccessError, acquire_service_entry,
    begin_service_invocation, end_service_invocation, get_service,
    mint_internal_invocation_claims, reset_envelope,
    reset_internal_invocation_claims, service_binding, service_callers,
    set_envelope, set_internal_invocation_claims,
    set_service,
)
from factory.memory.mcp.contracts.migration_import import MemoryImportInput
from factory.memory.runtime.adapters.memory import InMemoryStore
from factory.memory.runtime.migration_import import (
    ERR_DIGEST, ERR_KIND, canonical_target_digest,
)
from factory.memory.runtime.partition import derive_memory_user_id
from factory.memory.runtime.runtime import MemoryRuntime
from factory.memory.server import create_mcp_server

_AUDIENCE, _TARGET = "memory", "memory_import_record"
_BINDING_FIELDS = (
    "tenant_id", "owner_id", "source_adapter", "source_fingerprint",
    "plan_digest", "kind", "source_record_id", "target_digest",
)


def _fake_invoker():
    documents: dict[str, dict] = {}

    def invoke(name, **kwargs):
        if name == "storage_doc_get":
            data = documents.get(kwargs["doc_id"])
            return {"data": data} if data else {}
        assert name == "storage_doc_create_or_match"
        existing = documents.get(kwargs["doc_id"])
        if existing is None:
            documents[kwargs["doc_id"]] = kwargs["data"]
            return {"status": "created"}
        return {"status": "matched" if existing["content_hash"]
                == kwargs["content_hash"] else "conflict"}

    return invoke


@pytest.fixture
def runtime() -> MemoryRuntime:
    return MemoryRuntime(InMemoryStore())


@pytest.fixture
def tool(runtime):
    tools = {t.name: t for t in asyncio.run(create_mcp_server(runtime).list_tools())}
    return tools[_TARGET].fn


@pytest.fixture
def invoker():
    previous = get_service("tool_invoker")
    set_service("tool_invoker", _fake_invoker())
    try:
        yield
    finally:
        set_service("tool_invoker", previous)


def _args(**changes) -> dict:
    tags = changes.pop("tags", ["alpha", "beta"])
    base = {
        "tenant_id": "tenant-1", "owner_id": "owner-1",
        "source_adapter": "kirocrew-v1", "source_fingerprint": "a" * 64,
        "plan_digest": "b" * 64, "kind": "memory",
        "source_record_id": "c" * 64, "subtype": "semantic",
        "content": "durable knowledge", "key": "sem-key-1", "tags": list(tags),
    }
    base.update(changes)
    base["target_digest"] = changes.get("target_digest") or canonical_target_digest(
        tenant_id=base["tenant_id"], owner_id=base["owner_id"],
        kind=base["kind"], subtype=base["subtype"], content=base["content"],
        key=base["key"], tags=base["tags"],
    )
    return base


def _dispatch(fn, args: dict, *, caller="migration", binding=None):
    """Replay the native protected-dispatch permit flow inside an event loop
    (the permit machinery reads ``asyncio.current_task()``)."""
    binding = binding if binding is not None else MigrationImportBinding(
        **{k: args[k] for k in _BINDING_FIELDS})

    async def _run():
        claims = mint_internal_invocation_claims(
            caller=caller, audience=_AUDIENCE, target_tool=_TARGET,
            binding=binding, target=fn)
        token = set_internal_invocation_claims(claims)
        envelope_token = set_envelope({
            "tenant_id": args["tenant_id"], "principal_id": args["owner_id"],
            "session_id": "migration-session", "thread_id": "migration-thread",
        })
        try:
            state = begin_service_invocation(
                fn, audience=_AUDIENCE, target_tool=_TARGET, arguments=args)
            entry = acquire_service_entry(fn)
            try:
                return fn(**args, _service_entry_authorization=entry)
            finally:
                end_service_invocation(state)
        finally:
            reset_envelope(envelope_token)
            reset_internal_invocation_claims(token)

    return asyncio.run(_run())


def test_tool_is_bound_to_migration_caller_and_migration_import(tool) -> None:
    assert service_callers(tool) == frozenset({"migration"})
    assert service_binding(tool) == "migration_import"


def test_unauthorized_access_precedes_validation_and_effects(runtime, tool) -> None:
    # DTO-invalid AND effectful: authz raises before validation/store runs.
    with pytest.raises(ServiceOnlyAccessError):
        tool(
            tenant_id="t", owner_id="o", source_adapter="x",
            source_fingerprint="a" * 64, plan_digest="b" * 64, kind="memory",
            source_record_id="c" * 64, target_digest="d" * 64, subtype="bogus",
            content="", key="", tags=[], extra=True)
    assert runtime.stats().total_memories == 0


def test_exact_binding_success_imports_target_native_record(runtime, tool, invoker) -> None:
    result = _dispatch(tool, _args())
    assert result.ok and result.data.imported is True
    assert result.data.outcome == "imported"
    memory = runtime.get(result.data.memory_id)
    assert memory is not None and memory.content == "durable knowledge"
    assert memory.user_id == derive_memory_user_id("owner-1", "global")
    assert memory.metadata["import_source_record_id"] == "c" * 64
    assert memory.metadata["import_source_adapter"] == "kirocrew-v1"
    assert not any("path" in key.lower() for key in memory.metadata)


def test_digest_mismatch_fails_closed_before_write(runtime, tool, invoker) -> None:
    result = _dispatch(tool, _args(target_digest="f" * 64))
    assert result.ok and result.data.imported is False
    assert result.data.error == ERR_DIGEST
    assert runtime.stats().total_memories == 0


def test_non_memory_kind_rejected_before_write(runtime, tool, invoker) -> None:
    result = _dispatch(tool, _args(kind="lessons"))
    assert result.ok and result.data.imported is False
    assert result.data.error == ERR_KIND
    assert runtime.stats().total_memories == 0


def test_owner_isolation_partitions_records(runtime, tool, invoker) -> None:
    first = _dispatch(tool, _args(owner_id="owner-a"))
    second = _dispatch(tool, _args(owner_id="owner-b"))
    left, right = runtime.get(first.data.memory_id), runtime.get(second.data.memory_id)
    assert first.data.memory_id != second.data.memory_id
    assert left.user_id == derive_memory_user_id("owner-a", "global")
    assert right.user_id == derive_memory_user_id("owner-b", "global")
    assert left.user_id != right.user_id
    scoped = runtime.retrieve(user_id=left.user_id, query="durable", min_relevance=0.0)
    assert scoped and all(m.user_id == left.user_id for m in scoped)


def test_replay_returns_same_record_without_second_write(runtime, tool, invoker) -> None:
    args = _args()
    first = _dispatch(tool, dict(args))
    second = _dispatch(tool, dict(args))
    assert first.data.outcome == "imported" and second.data.outcome == "replayed"
    assert first.data.memory_id == second.data.memory_id
    assert runtime.stats().total_memories == 1


