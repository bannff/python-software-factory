from __future__ import annotations

from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.interface import CompletionBinding, ToolCatalog
from factory.session.runtime.adapters.completion_sql import SQLCompletionStore
from factory.session.runtime.adapters.sql import SQLSessionStore
from factory.session.runtime.completion import CompletionLifecycle
from factory.session.runtime.lifecycle import SessionLifecycle
from factory.session.runtime.runtime import SessionRuntime
from factory.session.server import create_tool_catalog
from factory.storage.interface import StorageRuntime


def test_workflow_records_completion_only_with_exact_binding(tmp_path) -> None:
    sql = StorageRuntime().get_sql_store("sqlite", db_path=str(tmp_path / "db.sqlite"))
    store = SQLSessionStore(sql)
    lifecycle = SessionLifecycle(store)
    origin = lifecycle.create("tenant", "owner", "origin", "agent", "model")
    completion = CompletionLifecycle(SQLCompletionStore(sql), store)
    child = create_tool_catalog(SessionRuntime(lifecycle, completion))
    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["session"])
    aggregator._lazy._cache["session"] = child
    native = NativeEnvelopeInvoker(aggregator)
    summary = "done"
    digest = completion.digest("ok", summary)
    arguments = {
        "tenant_id": "tenant", "owner_id": "owner",
        "session_id": origin.session_id, "run_id": "run:1",
        "revision": 1, "result_digest": digest,
        "outcome": "ok", "summary": summary,
    }
    denied = native.for_caller("workflow")(
        {"brick_name": "session", "tool_name": "record_completion"},
        arguments=arguments, idempotency_key="denied",
        envelope={"tenant_id": "tenant", "principal_id": "owner"},
    )
    assert denied["ok"] is False
    binding = CompletionBinding(**{
        key: arguments[key] for key in (
            "tenant_id", "owner_id", "session_id", "run_id",
            "revision", "result_digest",
        )
    })
    accepted = native.for_caller("workflow")(
        {"brick_name": "session", "tool_name": "record_completion"},
        arguments=arguments, idempotency_key="accepted",
        envelope={"tenant_id": "tenant", "principal_id": "owner"},
        completion=binding.__dict__ if hasattr(binding, "__dict__") else {
            field: getattr(binding, field) for field in binding.__dataclass_fields__
        },
    )
    assert accepted["ok"] is True, accepted
    assert [item.run_id for item in completion.pending(
        "tenant", "owner", origin.session_id,
    )] == ["run:1"]
