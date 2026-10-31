"""Canonical managed graph Workflow tests."""
from __future__ import annotations

from pathlib import Path

import pytest
from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.execution.adapters import create_executor
from factory.workflow.runtime.execution_engines import (
    ExecutionEngineRegistry, ExecutionEngineSpec,
)
from factory.workflow.runtime.task_models import TaskOutcomePolicy
from factory.workflow.runtime.models import Settings
from factory.workflow.runtime.operations import WorkflowError
from factory.workflow.runtime.runtime import WorkflowRuntime
from factory.workflow.runtime.storage.sqlite import SqliteWorkflowStorage


class GraphInvoker:
    def __init__(
        self, output: dict | None = None, *, cancel_outcome: str = "cancel_requested",
        cancel_raises: bool = False,
    ) -> None:
        self.calls: list[tuple] = []
        self.bindings: list[dict | None] = []
        self.output = output or {"status": "completed", "result": {"value": 7}}
        self.cancel_outcome = cancel_outcome
        self.cancel_raises = cancel_raises

    def invoke(
        self, *, target, arguments, idempotency_key, envelope, attempt=None,
    ):
        self.calls.append((target, arguments, idempotency_key, envelope))
        self.bindings.append(attempt)
        if target.tool_name == "cancel_strands_graph_attempt":
            if self.cancel_raises:
                raise ConnectionError("Agent process unavailable")
            output = {
                "schema_version": "v1", "ok": True,
                "data": {**arguments, "outcome": self.cancel_outcome},
                "error": None, "idempotency_key": None,
            }
        else:
            output = self.output
        return {"ok": True, "result": {
            "kind": "tool", "content": [], "meta": {},
            "structured_content": output,
        }}


def runtime(tmp_path: Path, invoker: GraphInvoker, engine_id: str = "strands_graph") -> WorkflowRuntime:
    config = tmp_path / "config"
    config.mkdir()
    storage = SqliteWorkflowStorage(config / "state.db")
    storage.init_schema()
    settings = Settings()
    return WorkflowRuntime(
        config_dir=config,
        settings=settings,
        settings_raw=settings.model_dump(),
        workflows=[],
        storage=storage,
        executor=create_executor(),
        tool_invoker=invoker,
        execution_engines=ExecutionEngineRegistry([ExecutionEngineSpec(
            engine_id=engine_id,
            invoke_target={"brick_name": "agent", "tool_name": f"execute_{engine_id}_attempt"},
            cancel_target={"brick_name": "agent", "tool_name": f"cancel_{engine_id}_attempt"},
            outcome=TaskOutcomePolicy(
                success={"pointer": "/status", "equals": "completed"},
                retryable={"pointer": "/retryable", "equals": True},
                error_pointer="/error",
            ),
        )]),
    )


DIGEST = "a" * 64


def descriptor(source_id: str = "graph") -> dict:
    return {"inline": {"opaque_source": source_id}, "reference": None}


def start(owner: WorkflowRuntime, graph_id: str = "graph", run_key: str = "key"):
    return owner.enroll_execution(
        engine_id="strands_graph", request=descriptor(graph_id),
        provider_request_digest=DIGEST, run_key=run_key,
        envelope=Envelope(tenant_id="tenant"),
    )


def test_managed_graph_is_one_canonical_named_mcp_attempt(tmp_path: Path) -> None:
    invoker = GraphInvoker()
    owner = runtime(tmp_path, invoker)
    result = start(owner)
    assert result["run_id"].startswith("wfr:v1:")
    assert result["attempt_id"].startswith("wfa:v1:")
    assert result["attempt_revision"] == 1
    assert result["status"] == "succeeded"
    target, arguments, key, _envelope = invoker.calls[0]
    assert (target.brick_name, target.tool_name) == ("agent", "execute_strands_graph_attempt")
    assert arguments["workflow_run_id"] == result["run_id"]
    assert arguments["attempt_id"] == result["attempt_id"]
    assert key == result["attempt_id"]
    assert arguments["revision"] == result["attempt_revision"]
    assert arguments["request"] == descriptor()
    assert arguments["provider_request_digest"] == DIGEST
    assert invoker.bindings[0] == {
        "workflow_run_id": result["run_id"], "attempt_id": result["attempt_id"],
        "revision": 1, "engine_id": "strands_graph",
        "registration_digest": result["registration_digest"],
        "request_digest": result["request_digest"],
        "provider_request_digest": DIGEST,
    }
    persisted = owner.get_run(run_id=result["run_id"], envelope=Envelope())
    assert persisted["result"]["task_result"]["status"] == "completed"
    snapshot = owner.durable_storage.load_workflow_version(
        persisted["workflow_version_id"],
    )
    assert len(snapshot.steps) == 1
    assert snapshot.steps[0].task_mode == "named_mcp"
    assert snapshot.steps[0].max_attempts == 2
    assert snapshot.steps[0].service_binding == "execution"


def test_run_key_replay_is_idempotent_and_conflict_is_rejected(tmp_path: Path) -> None:
    invoker = GraphInvoker()
    owner = runtime(tmp_path, invoker)
    first = start(owner)
    replay = start(owner)
    assert replay["run_id"] == first["run_id"]
    assert len(invoker.calls) == 1
    with pytest.raises(WorkflowError, match="run-key conflict"):
        owner.enroll_execution(
            engine_id="strands_graph", request=descriptor("other"),
            provider_request_digest="b" * 64, run_key="key",
            envelope=Envelope(tenant_id="tenant"),
        )


@pytest.mark.parametrize("graph_id", ["security-analysis", "supply-planning"])
def test_unrelated_domains_use_identical_path(tmp_path: Path, graph_id: str) -> None:
    invoker = GraphInvoker()
    result = start(runtime(tmp_path, invoker), graph_id=graph_id)
    assert result["status"] == "succeeded"
    assert invoker.calls[0][1]["request"] == descriptor(graph_id)


def test_failed_agent_outcome_is_authoritative_failure(tmp_path: Path) -> None:
    owner = runtime(tmp_path, GraphInvoker({"status": "failed", "error": "boom"}))
    result = start(owner)
    assert result["status"] == "failed"
    assert "boom" in result["error"]
    attempt = owner.durable_storage.list_task_attempts(run_id=result["run_id"])[0]
    assert attempt["status"] == "failed"


def test_configured_engine_enrolls_and_reports_capability(tmp_path: Path) -> None:
    config = tmp_path / "configured"
    config.mkdir()
    (config / "settings.yaml").write_text("""
storage:
  sqlite:
    filename: state.db
execution_engines:
  engines:
    - engine_id: strands_graph
      invoke_target:
        brick_name: agent
        tool_name: execute_strands_graph_attempt
      cancel_target:
        brick_name: agent
        tool_name: cancel_strands_graph_attempt
      outcome:
        success:
          pointer: /status
          equals: completed
        retryable:
          pointer: /retryable
          equals: true
        error_pointer: /error
""")
    invoker = GraphInvoker()
    owner = WorkflowRuntime.from_config_dir(config, tool_invoker=invoker)

    engines = owner.get_capabilities()["feature_flags"]["inhouse_execution_engines"]
    assert [engine["engine_id"] for engine in engines] == ["strands_graph"]
    assert start(owner)["status"] == "succeeded"
    assert invoker.calls[0][0].tool_name == "execute_strands_graph_attempt"


def test_empty_engine_registry_rejects_unconfigured_enrollment(tmp_path: Path) -> None:
    config = tmp_path / "empty"
    config.mkdir()
    (config / "settings.yaml").write_text("storage: {sqlite: {filename: state.db}}\n")
    owner = WorkflowRuntime.from_config_dir(config, tool_invoker=GraphInvoker())

    with pytest.raises(ValueError, match="unknown execution engine: strands_graph"):
        start(owner)
