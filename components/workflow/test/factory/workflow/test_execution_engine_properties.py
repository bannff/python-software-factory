"""Stateful properties for provider-neutral execution enrollment and journaling."""
from __future__ import annotations

import tempfile
import threading
from pathlib import Path

from hypothesis import settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, precondition, rule
from factory.workflow.runtime.canonical import canonical_loads
from factory.workflow.runtime.envelope import Envelope

from factory.workflow.runtime.execution_engines import ExecutionEngineRegistry

from .execution_engine_support import DIGEST, ENGINES, BlockingInvoker, enroll, event_values, runtime, spec


class ExecutionEngineMachine(RuleBasedStateMachine):
    """Exercise replay, owner fencing, journal ordering, and frozen cancellation for both engines."""
    def __init__(self):
        super().__init__()
        self.root = Path(tempfile.mkdtemp())
        self.owner = self.invoker = self.engine = self.result = self.thread = None
        self.errors: list[BaseException] = []
        self.events: list[dict] = []
        self.terminal = self.cancelled = False

    @initialize(engine=st.sampled_from(ENGINES))
    def start(self, engine):
        self.engine, self.invoker = engine, BlockingInvoker()
        self.owner = runtime(self.root, self.invoker)
        self.thread = threading.Thread(target=self._enroll); self.thread.start()
        assert self.invoker.started.wait(timeout=5)
        record = self.owner.durable_storage.get_run_by_key(run_key=f"key-{engine}")
        attempt = self.owner.durable_storage.list_task_attempts(run_id=record.run_id)[0]
        self.result = {"run_id": record.run_id, "attempt_id": attempt["attempt_id"],
            "registration_digest": self.owner.get_capabilities()["feature_flags"]
            ["inhouse_execution_engines"][0 if engine == ENGINES[0] else 1]["registration_digest"],
            "request_digest": canonical_loads(attempt["input_json"])["request_digest"]}

    def _enroll(self):
        try: enroll(self.owner, self.engine)
        except BaseException as exc: self.errors.append(exc)

    @rule()
    @precondition(lambda s: not s.events and not s.terminal and not s.cancelled)
    def append_first(self):
        raw = {"engine": self.engine, "sequence": 0}
        assert self.owner.append_execution_event(**event_values(self.owner, self.result, self.engine, 0, raw))["appended"]
        self.events.append(raw)

    @rule()
    @precondition(lambda s: bool(s.events) and not s.terminal and not s.cancelled)
    def duplicate_or_conflict(self):
        values = event_values(self.owner, self.result, self.engine, 0, self.events[0])
        assert not self.owner.append_execution_event(**values)["appended"]
        values["raw_evidence"] = {"conflict": True}
        try: self.owner.append_execution_event(**values)
        except ValueError as exc: assert "conflict" in str(exc)
        else: raise AssertionError("divergent duplicate must conflict")

    @rule()
    @precondition(lambda s: bool(s.events) and not s.terminal and not s.cancelled)
    def append_terminal(self):
        raw = {"engine": self.engine, "sequence": len(self.events), "terminal": True}
        assert self.owner.append_execution_event(**event_values(self.owner, self.result, self.engine,
            len(self.events), raw, True))["appended"]
        self.events.append(raw); self.terminal = True

    @rule()
    @precondition(lambda s: bool(s.events))
    def stale_revision_rejected(self):
        values = event_values(self.owner, self.result, self.engine, len(self.events), {"stale": True})
        values["revision"] += 1
        try: self.owner.append_execution_event(**values)
        except ValueError as exc: assert "stale" in str(exc)
        else: raise AssertionError("stale revision must be rejected")

    @rule()
    @precondition(lambda s: s.thread is not None and s.thread.is_alive() and not s.cancelled)
    def cancel_uses_frozen_provider(self):
        cancelled = self.owner.cancel_run(run_id=self.result["run_id"], reason="stop", envelope=Envelope(tenant_id="tenant"))
        assert cancelled["status"] == "cancelled"
        assert any(c[0].tool_name == f"cancel_{self.engine}_attempt" for c in self.invoker.calls)
        self.cancelled = True

    @rule()
    @precondition(lambda s: s.owner is not None)
    def live_registry_mutation_does_not_change_frozen_binding(self):
        """A compact mutation property: the persisted target remains authoritative."""
        self.owner.execution_engines = ExecutionEngineRegistry([spec("replacement")])
        run = self.owner.get_run(run_id=self.result["run_id"], envelope=Envelope())
        snapshot = self.owner.durable_storage.load_workflow_version(run["workflow_version_id"])
        assert snapshot.steps[0].tool_target.tool_name == f"execute_{self.engine}_attempt"

    @rule()
    def observe(self):
        """Keep the generated sequence valid after a terminal cancellation."""
        return None

    @invariant()
    def journal_is_contiguous_and_has_at_most_one_terminal(self):
        if not self.owner: return
        rows = self.owner.get_execution_events(workflow_run_id=self.result["run_id"])
        assert [row["sequence"] for row in rows] == list(range(len(rows)))
        assert sum(row["terminal"] for row in rows) <= 1

    def teardown(self):
        if self.invoker: self.invoker.release.set()
        if self.thread: self.thread.join(timeout=5)
        assert not self.errors


TestExecutionEngineMachine = ExecutionEngineMachine.TestCase
TestExecutionEngineMachine.settings = settings(max_examples=50, stateful_step_count=8, deadline=None)
