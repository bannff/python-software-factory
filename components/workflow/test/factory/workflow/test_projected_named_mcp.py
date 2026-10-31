"""Projected-input, outcome, idempotency, and terminal-result contracts."""
from __future__ import annotations

import sqlite3
import string
import tempfile
from pathlib import Path

import yaml
from hypothesis import given, strategies as st

from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.runtime import WorkflowRuntime

TARGETS = {"work": {"brick_name": "demo", "tool_name": "work"}}

class SequenceInvoker:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def invoke(self, *, target, arguments, idempotency_key, envelope):
        self.calls.append((target, arguments, idempotency_key, envelope))
        output = self.outputs[min(len(self.calls) - 1, len(self.outputs) - 1)]
        return {"ok": True, "result": {
            "kind": "tool", "content": [], "meta": {},
            "structured_content": output,
        }}

def _config(tmp_path: Path, definition: dict) -> Path:
    config = tmp_path / "config"
    (config / "workflows").mkdir(parents=True)
    (config / "settings.yaml").write_text(yaml.safe_dump({
        "storage": {"backend": "sqlite", "sqlite": {"filename": "state.db"}},
        "durable_tasks": {"allowlist": TARGETS},
    }))
    (config / "workflows" / "workflow.yaml").write_text(yaml.safe_dump(definition))
    return config

def _step(**updates) -> dict:
    value = {"id": "work", "kind": "task", "task_mode": "named_mcp",
             "task_type": "work"}
    value.update(updates)
    return value


@given(
    selected=st.integers(),
    extra=st.dictionaries(
        st.text(alphabet=string.ascii_lowercase, min_size=2, max_size=8)
        .filter(lambda key: key not in {
            "selected", "request_id", "body", "subject", "recipients", "to",
            "cc", "bcc", "html", "text", "message", "query",
            "provider_request", "provider_response", "attachments",
        }),
        st.integers(), max_size=5,
    ),
)
def test_v2_projects_only_declared_input_and_binds_attempt_id(
    selected: int, extra: dict,
) -> None:
    definition = {
        "schema_version": "v2", "id": "wf", "name": "WF",
        "result_projection": {
            "selected": {"$ref": "workflow-run:///input#/selected"},
            "output": {"$ref": "workflow-step:///work/output#/value"},
            "attempt": {"$ref": "workflow-step:///work/evidence#/gateway/attempt_id"},
        },
        "steps": [_step(
            idempotency_key_argument="request_id",
            task_payload={
                "value": {"$ref": "workflow-run:///input#/selected"},
            },
            task_outcome={"success": {"pointer": "/status", "equals": "ok"}},
        )],
    }
    invoker = SequenceInvoker([{"status": "ok", "value": selected}])
    runtime = WorkflowRuntime.from_config_dir(
        _config(Path(tempfile.mkdtemp()), definition), tool_invoker=invoker,
    )
    started = runtime.start_run(
        workflow_name_or_id="wf", input={**extra, "selected": selected},
        run_key="projected", envelope=Envelope(),
    )
    target, arguments, key, _ = invoker.calls[0]
    assert target.tool_name == "work"
    assert arguments == {"value": selected, "request_id": key}
    final = runtime.get_run(run_id=started["run_id"], envelope=Envelope())
    assert final["result"]["task_result"] == {
        "selected": selected, "output": selected, "attempt": key,
    }
    with sqlite3.connect(runtime.storage.path) as conn:
        base, exact = conn.execute(
            "SELECT s.input_json,a.input_json FROM step_executions s "
            "JOIN task_attempts a USING(step_execution_id)",
        ).fetchone()
    assert yaml.safe_load(base) == {"value": selected}
    assert yaml.safe_load(exact) == arguments

def test_domain_outcome_retries_with_new_attempt_binding(tmp_path: Path) -> None:
    definition = {
        "schema_version": "v2", "id": "wf", "name": "WF", "steps": [_step(
            max_attempts=2, idempotency_key_argument="request_id",
            task_outcome={
                "success": {"pointer": "/status", "equals": "ok"},
                "retryable": {"pointer": "/retry", "equals": True},
                "error_pointer": "/error",
            },
        )],
    }
    invoker = SequenceInvoker([
        {"status": "error", "retry": True, "error": "try later"},
        {"status": "ok", "value": 9},
    ])
    runtime = WorkflowRuntime.from_config_dir(
        _config(tmp_path, definition), tool_invoker=invoker,
    )
    started = runtime.start_run(
        workflow_name_or_id="wf", input={"private_value": "not-forwarded"},
        run_key="retry", envelope=Envelope(),
    )
    assert started["status"] == "succeeded"
    attempts = runtime.durable_storage.list_task_attempts(run_id=started["run_id"])
    assert [item["status"] for item in attempts] == ["failed", "succeeded"]
    assert [call[1] for call in invoker.calls] == [
        {"request_id": attempts[0]["attempt_id"]},
        {"request_id": attempts[1]["attempt_id"]},
    ]
    assert [call[2] for call in invoker.calls] == [
        attempts[0]["attempt_id"], attempts[1]["attempt_id"],
    ]

def test_outcome_failure_is_not_journaled_as_success(tmp_path: Path) -> None:
    definition = {
        "schema_version": "v2", "id": "wf", "name": "WF", "steps": [_step(
            max_attempts=2,
            task_outcome={
                "success": {"pointer": "/status", "equals": "ok"},
                "retryable": {"pointer": "/retry", "equals": True},
                "error_pointer": "/error",
            },
        )],
    }
    invoker = SequenceInvoker([{"status": "error", "retry": False, "error": "bad"}])
    runtime = WorkflowRuntime.from_config_dir(
        _config(tmp_path, definition), tool_invoker=invoker,
    )
    started = runtime.start_run(
        workflow_name_or_id="wf", input={}, run_key="failed", envelope=Envelope(),
    )
    assert started["status"] == "failed"
    attempts = runtime.durable_storage.list_task_attempts(run_id=started["run_id"])
    assert attempts[0]["status"] == "failed" and attempts[0]["error"] == "bad"
    assert len(invoker.calls) == 1


def test_idempotency_argument_collision_fails_before_invocation(tmp_path: Path) -> None:
    definition = {
        "schema_version": "v2", "id": "wf", "name": "WF", "steps": [_step(
            idempotency_key_argument="request_id",
            task_payload={"request_id": "caller-owned"},
        )],
    }
    invoker = SequenceInvoker([{"value": 1}])
    runtime = WorkflowRuntime.from_config_dir(
        _config(tmp_path, definition), tool_invoker=invoker,
    )
    started = runtime.start_run(
        workflow_name_or_id="wf", input={}, run_key="collision", envelope=Envelope(),
    )
    assert started["status"] == "failed" and invoker.calls == []
