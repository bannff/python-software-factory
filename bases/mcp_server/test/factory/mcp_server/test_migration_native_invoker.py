"""Native Workflow → Migration → protected-target binding integration."""
from __future__ import annotations

from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.interface import get_service, set_service
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.migration.runtime.adapters.receipt_store_sql import SqlReceiptStore
from factory.migration.runtime.plan_records import PlanRecord
from factory.migration.runtime.preview import PreviewRuntime
from factory.migration.runtime.receipt_models import PlanIdentity
from factory.migration.runtime.source_models import SafeMemory, SourceKind, identity_of
from factory.migration.server import create_tool_catalog
from factory.storage.interface import StorageRuntime


def _runtime(tmp_path) -> PreviewRuntime:
    store = SqlReceiptStore(StorageRuntime().get_sql_store(
        "sqlite", db_path=str(tmp_path / "native-migration.db")))
    plan = PlanIdentity(
        tenant_id="tenant", owner_id="owner", adapter="kirocrew-v1",
        source_fingerprint="a" * 64, plan_digest="sha256:" + "b" * 64,
        kinds=("memory",),
    )
    payload = SafeMemory(
        kind="semantic", identity=identity_of("semantic", "native"),
        key="native", content="native invoker proof",
    )
    store.save_plan_records(plan, (
        PlanRecord.from_source(plan, SourceKind.MEMORY, payload),
    ))
    store.bind_plan(plan)
    return PreviewRuntime(None, store)


def test_native_workflow_apply_invokes_exact_migration_target_binding(tmp_path) -> None:
    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["migration"])
    aggregator._lazy._cache["migration"] = create_tool_catalog(_runtime(tmp_path))
    calls = []

    def factory(caller):
        assert caller == "migration"

        def invoke(target, **kwargs):
            calls.append((target, kwargs))
            return {"ok": True, "result": {"structured_content": {
                "schema_version": "v1", "ok": True,
                "data": {"imported": True, "outcome": "imported"},
            }}}
        return invoke

    values = {
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
    binding = {key: values[key] for key in (
        "workflow_run_id", "attempt_id", "revision", "engine_id",
        "registration_digest", "request_digest", "provider_request_digest",
    )}
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", factory)
    try:
        result = NativeEnvelopeInvoker(aggregator).for_caller("workflow")(
            {"brick_name": "migration", "tool_name": "migration_apply_execution"},
            arguments=values, idempotency_key="attempt-1",
            envelope={
                "tenant_id": "tenant", "principal_id": "owner",
                "session_id": "session", "thread_id": "thread", "run_id": "run-1",
            },
            attempt=binding,
        )
    finally:
        set_service("tool_invoker_for_caller", previous)
    assert result["ok"] is True
    output = result["result"]["structured_content"]["data"]
    assert output["status"] == "completed" and output["imported"] == 1
    assert calls[0][0] == {"brick_name": "memory", "tool_name": "memory_import_record"}
    assert calls[0][1]["migration_import"] == {
        key: calls[0][1]["arguments"][key] for key in (
            "tenant_id", "owner_id", "source_adapter", "source_fingerprint",
            "plan_digest", "kind", "source_record_id", "target_digest",
        )
    }
