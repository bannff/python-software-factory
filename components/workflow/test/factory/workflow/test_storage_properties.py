"""Property-based tests for SqliteWorkflowStorage using Hypothesis."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant

from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.storage.sqlite import SqliteWorkflowStorage

_alnum = st.characters(whitelist_categories=("L", "N"))
run_ids = st.text(min_size=1, max_size=20, alphabet=_alnum)
workflow_ids = st.text(min_size=1, max_size=20, alphabet=_alnum)
statuses = st.sampled_from(["pending", "running", "waiting", "succeeded", "failed", "cancelled"])
event_types = st.sampled_from(["step.started", "step.completed", "signal.received", "error"])

def _storage() -> SqliteWorkflowStorage:
    s = SqliteWorkflowStorage(Path(tempfile.mktemp(suffix=".db")))
    s.init_schema()
    return s

def _now() -> datetime:
    return datetime.now(timezone.utc)

def _create(s, rid="r1", wid="wf1", **kw):
    return s.create_run(
        run_id=rid, workflow_id=wid, workflow_version=1,
        tenant_id=None, input=kw.get("input", {}), envelope=Envelope(), now=_now(),
    )


# \u2500\u2500 @given property tests \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

@settings(max_examples=50)
@given(rid=run_ids, wid=workflow_ids)
def test_create_then_get_roundtrip(rid, wid):
    """create_run then get_run returns the same run with status 'running'."""
    s = _storage()
    created = _create(s, rid, wid, input={"k": "v"})
    fetched = s.get_run(run_id=rid)
    assert fetched is not None
    assert fetched.run_id == rid
    assert fetched.workflow_id == wid
    assert fetched.status == "running"
    assert fetched.input == {"k": "v"}
    assert created.run_id == fetched.run_id


@settings(max_examples=50)
@given(rid=run_ids, status=statuses)
def test_update_run_changes_status(rid, status):
    """update_run correctly changes the run status."""
    s = _storage()
    _create(s, rid)
    updated = s.update_run(
        run_id=rid, status=status, current_step_id=None,
        waiting_for_event_type=None, last_event_id=None,
        result=None, error=None, now=_now(),
    )
    assert updated.status == status
    assert s.get_run(run_id=rid).status == status


@settings(max_examples=50)
@given(rid=run_ids)
def test_duplicate_create_returns_existing(rid):
    """create_run with duplicate run_id returns the existing run."""
    s = _storage()
    first = _create(s, rid, "wf1", input={"first": True})
    second = _create(s, rid, "wf2", input={"second": True})
    assert second.run_id == first.run_id
    assert second.workflow_id == "wf1"


@settings(max_examples=50)
@given(rid=run_ids, etype=event_types)
def test_append_event_then_get_events(rid, etype):
    """append_event then get_events_since(0) returns the event."""
    s = _storage()
    _create(s, rid)
    evt = s.append_event(
        run_id=rid, event_type=etype, payload={"x": 1},
        envelope=Envelope(), now=_now(),
    )
    events = s.get_events_since(run_id=rid, after_event_id=0)
    assert any(e.id == evt.id and e.event_type == etype for e in events)


@settings(max_examples=50)
@given(rid=run_ids)
def test_last_event_id_zero_when_no_events(rid):
    """get_last_event_id returns 0 for a run with no events."""
    s = _storage()
    _create(s, rid)
    assert s.get_last_event_id(run_id=rid) == 0


@settings(max_examples=50)
@given(rid=run_ids)
def test_last_event_id_tracks_appends(rid):
    """get_last_event_id returns the latest event ID after appending."""
    s = _storage()
    _create(s, rid)
    e1 = s.append_event(
        run_id=rid, event_type="step.started", payload={},
        envelope=Envelope(), now=_now(),
    )
    assert s.get_last_event_id(run_id=rid) == e1.id
    e2 = s.append_event(
        run_id=rid, event_type="step.completed", payload={},
        envelope=Envelope(), now=_now(),
    )
    assert s.get_last_event_id(run_id=rid) == e2.id
    assert e2.id > e1.id


# \u2500\u2500 Stateful test \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

class StorageStateMachine(RuleBasedStateMachine):
    """Stateful test: arbitrary create/update/list/event sequences."""

    def __init__(self):
        super().__init__()
        self.storage: SqliteWorkflowStorage | None = None
        self.runs: dict[str, str] = {}

    @initialize()
    def init_storage(self):
        self.storage = _storage()
        self.runs = {}

    @rule(rid=run_ids, wid=workflow_ids)
    def create_run(self, rid, wid):
        if rid in self.runs:
            return
        _create(self.storage, rid, wid)
        self.runs[rid] = "running"

    @rule(status=statuses)
    def update_random_run(self, status):
        if not self.runs:
            return
        rid = list(self.runs.keys())[0]
        self.storage.update_run(
            run_id=rid, status=status, current_step_id=None,
            waiting_for_event_type=None, last_event_id=None,
            result=None, error=None, now=_now(),
        )
        self.runs[rid] = status

    @rule()
    def list_runs(self):
        runs, _ = self.storage.list_runs(
            tenant_id=None, workflow_id=None, status=None, limit=1000, cursor=None,
        )
        assert len(runs) == len(self.runs)

    @rule(etype=event_types)
    def append_event(self, etype):
        if not self.runs:
            return
        rid = list(self.runs.keys())[0]
        evt = self.storage.append_event(
            run_id=rid, event_type=etype, payload={},
            envelope=Envelope(), now=_now(),
        )
        assert evt.run_id == rid

    @invariant()
    def run_count_matches(self):
        if not self.storage:
            return
        runs, _ = self.storage.list_runs(
            tenant_id=None, workflow_id=None, status=None, limit=1000, cursor=None,
        )
        assert len(runs) == len(self.runs)

    @invariant()
    def every_run_retrievable_with_correct_status(self):
        if not self.storage:
            return
        for rid, expected in self.runs.items():
            rec = self.storage.get_run(run_id=rid)
            assert rec is not None, f"Run {rid} should exist"
            assert rec.status == expected, f"{rid}: expected {expected}, got {rec.status}"

    @invariant()
    def nonexistent_run_returns_none(self):
        if not self.storage:
            return
        assert self.storage.get_run(run_id="__nonexistent__") is None


TestStorageStateful = StorageStateMachine.TestCase
TestStorageStateful.settings = settings(
    max_examples=30, deadline=None, stateful_step_count=20,
)
