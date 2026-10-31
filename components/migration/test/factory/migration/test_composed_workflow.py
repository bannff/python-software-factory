"""Composed real WorkflowRuntime proof for multi-page Migration execution."""
from __future__ import annotations

from pathlib import Path

import yaml

from factory.migration.mcp.execution_contracts import ApplyPageRequest
from factory.migration.runtime.adapters.receipt_store_sql import SqlReceiptStore
from factory.migration.runtime.apply_execution import apply_plan_page
from factory.migration.runtime.lifecycle import project_progress, start_plan
from factory.migration.runtime.plan_records import PlanRecord
from factory.migration.runtime.receipt_models import PlanIdentity
from factory.migration.runtime.source_models import (
    SafeLesson, SafeMemory, SourceKind, identity_of,
)
from factory.storage.interface import StorageRuntime
from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.runtime import WorkflowRuntime


def _config(root: Path) -> Path:
    config = root / "workflow"
    config.mkdir()
    (config / "settings.yaml").write_text(yaml.safe_dump({
        "storage": {"backend": "sqlite", "sqlite": {"filename": "workflow.db"}},
        "execution_engines": {"engines": [{
            "engine_id": "migration_import",
            "invoke_target": {
                "brick_name": "migration", "tool_name": "migration_apply_execution"},
            "outcome": {
                "success": {"pointer": "/status", "equals": "completed"},
                "continuation": {"pointer": "/status", "equals": "partial"},
                "retryable": {"pointer": "/retryable", "equals": True},
                "error_pointer": "/error",
            },
            "max_attempts": 3, "max_continuations": 1000,
        }]},
    }))
    return config


def _migration_store(path: Path) -> tuple[SqlReceiptStore, PlanIdentity]:
    store = SqlReceiptStore(StorageRuntime().get_sql_store("sqlite", db_path=str(path)))
    plan = PlanIdentity(
        tenant_id="tenant", owner_id="owner", adapter="kirocrew-v1",
        source_fingerprint="a" * 64, plan_digest="sha256:" + "b" * 64,
        kinds=("memory", "lessons"),
    )
    memories = tuple(PlanRecord.from_source(
        plan, SourceKind.MEMORY, SafeMemory(
            kind="semantic", identity=identity_of("semantic", f"key-{index}"),
            key=f"key-{index}", content=f"content-{index}",
        )) for index in range(51))
    lesson = PlanRecord.from_source(
        plan, SourceKind.LESSONS, SafeLesson(
            identity=identity_of("lesson", "composed"),
            rule="Keep composed evidence", origin="jsonl",
        ))
    store.save_plan_records(plan, memories + (lesson,))
    store.bind_plan(plan)
    return store, plan


def _target_success(*_args, **_kwargs):
    return {"ok": True, "result": {"structured_content": {
        "schema_version": "v1", "ok": True,
        "data": {"imported": True, "outcome": "imported"},
    }}}


class MigrationExecutionInvoker:
    def __init__(self, store: SqlReceiptStore):
        self.store = store
        self.calls = 0

    def invoke(self, *, target, arguments, idempotency_key, envelope, attempt=None):
        del target, idempotency_key, attempt
        self.calls += 1
        output = apply_plan_page(
            self.store, _target_success, envelope.model_dump(mode="json"),
            ApplyPageRequest.model_validate(arguments["request"]),
        )
        return {"ok": True, "result": {
            "kind": "tool", "content": [], "meta": {},
            "structured_content": {
                "schema_version": "v1", "ok": True,
                "data": output.model_dump(mode="json"),
            },
        }}


def _enrollment_invoker(runtime: WorkflowRuntime):
    def invoke(_target, **kwargs):
        args = kwargs["arguments"]
        result = runtime.enroll_execution(
            engine_id=args["engine_id"], request=args["request"],
            provider_request_digest=args["provider_request_digest"],
            run_key=args["run_key"], envelope=Envelope.model_validate(args["envelope"]),
            execute=args["execute"], launch_metadata=args["launch_metadata"],
        )
        return {"ok": True, "result": {"structured_content": {
            "schema_version": "v1", "ok": True, "data": result,
        }}}
    return invoke


def _get_invoker(runtime: WorkflowRuntime):
    def invoke(_target, **kwargs):
        args = kwargs["arguments"]
        result = runtime.get_run(
            run_id=args["run_id"], envelope=Envelope.model_validate(args["envelope"]))
        return {"ok": True, "result": {"structured_content": {
            "schema_version": "v1", "ok": True, "data": result,
        }}}
    return invoke


def test_real_workflow_completes_replays_and_survives_restart(tmp_path) -> None:
    config = _config(tmp_path)
    migration_db = tmp_path / "migration.db"
    store, plan = _migration_store(migration_db)
    executor = MigrationExecutionInvoker(store)
    workflow = WorkflowRuntime.from_config_dir(config, tool_invoker=executor)
    envelope = {"tenant_id": "tenant", "principal_id": "owner"}
    started = start_plan(plan, _enrollment_invoker(workflow), envelope)
    assert started.status == "succeeded" and executor.calls == 3
    attempts = workflow.durable_storage.list_task_attempts(run_id=started.run_id)
    assert [row["status"] for row in attempts] == [
        "continued", "continued", "succeeded"]
    report = project_progress(store, _get_invoker(workflow), envelope, started.run_id)
    assert report.terminal_reason == "completed"
    assert sum(row.imported for row in report.progress) == 52
    assert [row.cursor for row in report.progress] == [51, 1]

    reopened_store = SqlReceiptStore(
        StorageRuntime().get_sql_store("sqlite", db_path=str(migration_db)))
    reopened_executor = MigrationExecutionInvoker(reopened_store)
    reopened_workflow = WorkflowRuntime.from_config_dir(
        config, tool_invoker=reopened_executor)
    replay = start_plan(plan, _enrollment_invoker(reopened_workflow), envelope)
    assert replay.run_id == started.run_id and replay.status == "succeeded"
    assert reopened_executor.calls == 0
    reopened = project_progress(
        reopened_store, _get_invoker(reopened_workflow), envelope, replay.run_id)
    assert reopened == report
