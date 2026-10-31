"""Hypothesis public-runtime state machine with reconstruction before each action."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import yaml
from hypothesis import settings
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, precondition, rule

from factory.workflow.runtime.canonical import canonical_loads
from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.operations import WorkflowError
from factory.workflow.runtime.runtime import WorkflowRuntime
from factory.workflow.runtime.task_ids import step_execution_id
from factory.workflow.runtime.task_refs import digest_json
from .restart_stateful_support import IdempotentInvoker, InvokerState, ProcessCrash

class PublicRestartMachine(RuleBasedStateMachine):
    @initialize()
    def setup(self):
        self.config = Path(tempfile.mkdtemp())
        (self.config / "workflows").mkdir()
        self._write_settings("demo")
        workflow = {
            "schema_version": "v2", "id": "wf", "name": "Workflow", "version": 1,
            "result_projection": {
                "input": {"$ref": "workflow-run:///input#/value"},
                "produced": {"$ref": "workflow-step:///produce/output#/value"},
                "attempt": {"$ref": "workflow-step:///consume/evidence#/gateway/attempt_id"},
            },
            "steps": [
                {"id": "produce", "kind": "task", "task_mode": "named_mcp",
                 "task_type": "produce", "lease_seconds": 1, "next": "wait",
                 "idempotency_key_argument": "request_id", "task_payload": {
                     "value": {"$ref": "workflow-run:///input#/value"},
                 }},
                {"id": "wait", "kind": "wait_for_event", "event_type": "continue",
                 "next": "consume"},
                {"id": "consume", "kind": "task", "task_mode": "named_mcp",
                 "task_type": "consume", "max_attempts": 2,
                 "idempotency_key_argument": "request_id",
                 "task_outcome": {"success": {"pointer": "/value", "equals": 7}},
                 "task_payload": {
                     "value": {"$ref": "workflow-step:///produce/output#/value"},
                 }},
            ],
        }
        unknown = {"id": "unknown", "name": "Unknown", "version": 1, "steps": [
            {"id": "missing", "kind": "task", "task_mode": "named_mcp",
             "task_type": "not-allowed"},
        ]}
        (self.config / "workflows" / "workflow.yaml").write_text(yaml.safe_dump(workflow))
        (self.config / "workflows" / "unknown.yaml").write_text(yaml.safe_dump(unknown))
        self.invoker_state = InvokerState()
        self.run_id = self.status = None
        self.attempt_ids = {}
        self.reclaim_proved = self.drifted = False
        self.envelope = Envelope(tenant_id="tenant", principal_id="principal",
                                 correlation_id="correlation")

    def _write_settings(self, brick: str) -> None:
        (self.config / "settings.yaml").write_text(yaml.safe_dump({
            "storage": {"backend": "sqlite", "sqlite": {"filename": "state.db"}},
            "durable_tasks": {"allowlist": {
                "produce": {"brick_name": brick, "tool_name": "produce"},
                "consume": {"brick_name": brick, "tool_name": "consume"},
            }},
        }))

    def _runtime(self) -> WorkflowRuntime:
        invoker = IdempotentInvoker(self.invoker_state)
        return WorkflowRuntime.from_config_dir(self.config, tool_invoker=invoker)

    def _expire_producer(self, runtime: WorkflowRuntime) -> dict:
        record = runtime.durable_storage.get_run_by_key(run_key="property-run")
        self.run_id = record.run_id
        before = runtime.durable_storage.list_task_attempts(run_id=self.run_id)[0]
        with sqlite3.connect(self.config / "state.db") as conn:
            conn.execute(
                "UPDATE task_attempts SET lease_expires_at=? WHERE attempt_id=?",
                ("2000-01-01T00:00:00+00:00", before["attempt_id"]),
            )
        return before

    @rule()
    def start_or_repeat(self):
        try:
            result = self._runtime().start_run(
                workflow_name_or_id="wf", input={"value": 7},
                run_key="property-run", envelope=self.envelope,
            )
        except ProcessCrash:
            before = self._expire_producer(self._runtime())
            result = self._runtime().resume_run(run_id=self.run_id, envelope=self.envelope)
            after = self._runtime().durable_storage.list_task_attempts(run_id=self.run_id)[0]
            keys = [call[2] for call in self.invoker_state.calls
                    if call[0].tool_name == "produce"]
            assert after["attempt_id"] == before["attempt_id"]
            assert after["revision"] > before["revision"]
            assert keys == [before["attempt_id"], before["attempt_id"]]
            self.reclaim_proved = True
            self._write_settings("drifted")
            self.drifted = True
        self.run_id = self.run_id or result["run_id"]
        assert result.get("run_id", self.run_id) == self.run_id
        self.status = result["status"]

    @rule()
    def unknown_target_is_loud(self):
        try:
            self._runtime().start_run(
                workflow_name_or_id="unknown", input={}, run_key="unknown-run",
                envelope=self.envelope,
            )
        except WorkflowError as exc:
            assert "disallowed" in str(exc)
        else:
            raise AssertionError("unknown named target was accepted")

    @precondition(lambda self: self.run_id is not None and self.status == "waiting")
    @rule()
    def emit_continue(self):
        self._runtime().emit_event(
            run_id=self.run_id, event_type="continue", payload={"ok": True},
            envelope=self.envelope,
        )

    @precondition(lambda self: self.run_id is not None and self.status not in {"succeeded", "failed", "cancelled"})
    @rule()
    def step(self):
        self.status = self._runtime().step_run(
            run_id=self.run_id, envelope=self.envelope,
        )["status"]

    @precondition(lambda self: self.run_id is not None and self.status not in {"succeeded", "failed", "cancelled"})
    @rule()
    def cancel(self):
        self.status = self._runtime().cancel_run(
            run_id=self.run_id, reason="property cancellation", envelope=self.envelope,
        )["status"]

    @precondition(lambda self: self.run_id is not None)
    @rule()
    def get_terminal_or_active(self):
        record = self._runtime().get_run(run_id=self.run_id, envelope=self.envelope)
        assert record["run_id"] == self.run_id
        self.status = record["status"]

    def _assert_integrity(self) -> None:
        with sqlite3.connect(self.config / "state.db") as conn:
            rows = conn.execute(
                "SELECT s.output_json,s.output_digest,s.evidence_json,a.evidence_digest "
                "FROM step_executions s JOIN task_attempts a USING(step_execution_id) "
                "WHERE s.status='succeeded' AND a.status='succeeded'",
            ).fetchall()
        for output_json, output_digest, evidence_json, evidence_digest in rows:
            output, evidence = canonical_loads(output_json), canonical_loads(evidence_json)
            assert digest_json(output) == output_digest
            assert evidence["output_sha256"] == output_digest
            assert digest_json(evidence) == evidence_digest

    @invariant()
    def durable_invariants(self):
        if self.run_id is None:
            return
        runtime = self._runtime()
        record = runtime.durable_storage.get_run_by_key(run_key="property-run")
        assert record.run_id == self.run_id and record.run_key == "property-run"
        assert self.reclaim_proved and self.drifted \
            and self.invoker_state.wrapper_count > 1
        snapshot = runtime.durable_storage.load_workflow_version(record.workflow_version_id)
        assert {step.tool_target.brick_name for step in snapshot.steps if step.tool_target} == {"demo"}
        rows = runtime.durable_storage.list_task_attempts(run_id=self.run_id)
        for row in rows:
            key = (row["step_execution_id"], row["attempt_number"])
            self.attempt_ids.setdefault(key, row["attempt_id"])
            assert self.attempt_ids[key] == row["attempt_id"]
        consume_id = step_execution_id(record.run_execution_id, "consume")
        consume = [row for row in rows if row["step_execution_id"] == consume_id]
        if consume:
            assert [row["attempt_number"] for row in consume] == [1, 2]
        calls = self.invoker_state.calls
        assert all(call[0].brick_name == "demo" for call in calls)
        assert all(call[3].principal_id == "principal" for call in calls)
        assert all(call[1]["value"] == 7 for call in calls)
        assert all(call[1]["request_id"] == call[2] for call in calls)
        assert all(set(call[1]) == {"value", "request_id"} for call in calls)
        assert all(count == 1 for count in self.invoker_state.commit_counts.values())
        if record.status == "succeeded":
            projection = record.result["task_result"]
            assert projection["input"] == projection["produced"] == 7
            assert projection["attempt"] == consume[-1]["attempt_id"]
        self._assert_integrity()


TestPublicRestart = PublicRestartMachine.TestCase
TestPublicRestart.settings = settings(max_examples=50, stateful_step_count=15, deadline=None)
