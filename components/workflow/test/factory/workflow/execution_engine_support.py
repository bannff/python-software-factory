"""Shared public-Workflow harness for polymorphic execution-engine QA."""
from __future__ import annotations

from pathlib import Path
import threading

from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.execution.adapters import create_executor
from factory.workflow.runtime.execution_engines import ExecutionEngineRegistry, ExecutionEngineSpec
from factory.workflow.runtime.models import Settings
from factory.workflow.runtime.runtime import WorkflowRuntime
from factory.workflow.runtime.storage.sqlite import SqliteWorkflowStorage
from factory.workflow.runtime.task_models import TaskOutcomePolicy

DIGEST = "a" * 64
ENGINES = ("strands_graph", "fake_compute")


def spec(engine_id: str, *, provider: str | None = None, cancel: bool = True) -> ExecutionEngineSpec:
    provider = provider or engine_id
    return ExecutionEngineSpec(
        engine_id=engine_id,
        invoke_target={"brick_name": "agent" if engine_id == "strands_graph" else "qa_fake",
                       "tool_name": f"execute_{provider}_attempt"},
        cancel_target=({"brick_name": "agent" if engine_id == "strands_graph" else "qa_fake",
                        "tool_name": f"cancel_{provider}_attempt"} if cancel else None),
        outcome=TaskOutcomePolicy(success={"pointer": "/status", "equals": "completed"},
                                  retryable={"pointer": "/retryable", "equals": True},
                                  error_pointer="/error"),
    )


class Invoker:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.bindings: list[dict | None] = []

    def invoke(self, *, target, arguments, idempotency_key, envelope, attempt=None):
        self.calls.append((target, arguments, idempotency_key, envelope))
        self.bindings.append(attempt)
        if target.tool_name.startswith("cancel_"):
            data = {**arguments, "outcome": "cancel_requested"}
        else:
            data = {"status": "completed", "result": {"provider": target.tool_name}}
        return {"ok": True, "result": {"kind": "tool", "content": [], "meta": {},
                "structured_content": {"schema_version": "v1", "ok": True,
                "data": data, "error": None, "idempotency_key": None}}}


class BlockingInvoker(Invoker):
    """Keeps one execution attempt running while journal and cancel APIs are tested."""
    def __init__(self) -> None:
        super().__init__()
        self.started, self.release = threading.Event(), threading.Event()

    def invoke(self, **kwargs):
        if not kwargs["target"].tool_name.startswith("cancel_"):
            self.started.set()
            assert self.release.wait(timeout=5)
        return super().invoke(**kwargs)


def runtime(tmp_path: Path, invoker: Invoker, *, specs: list[ExecutionEngineSpec] | None = None) -> WorkflowRuntime:
    config = tmp_path / "config"; config.mkdir(parents=True, exist_ok=True)
    storage = SqliteWorkflowStorage(config / "state.db"); storage.init_schema()
    settings = Settings()
    return WorkflowRuntime(config_dir=config, settings=settings, settings_raw=settings.model_dump(),
        workflows=[], storage=storage, executor=create_executor(), tool_invoker=invoker,
        execution_engines=ExecutionEngineRegistry(
            specs if specs is not None else [spec(name) for name in ENGINES]
        ))


def enroll(owner: WorkflowRuntime, engine_id: str, *, request: dict | None = None, key: str | None = None):
    return owner.enroll_execution(engine_id=engine_id,
        request=request or {"inline": {"provider": engine_id}, "reference": None},
        provider_request_digest=DIGEST, run_key=key or f"key-{engine_id}",
        envelope=Envelope(tenant_id="tenant"))


def event_values(owner: WorkflowRuntime, result: dict, engine_id: str, sequence: int, raw: dict, terminal=False):
    attempt = owner.durable_storage.list_task_attempts(run_id=result["run_id"])[0]
    return {"workflow_run_id": result["run_id"], "attempt_id": result["attempt_id"],
        "revision": attempt["revision"], "engine_id": engine_id,
        "registration_digest": result["registration_digest"], "request_digest": result["request_digest"],
        "provider_request_digest": DIGEST, "sequence": sequence, "terminal": terminal,
        "raw_evidence": raw, "safe_metadata": {"provider": engine_id}}
