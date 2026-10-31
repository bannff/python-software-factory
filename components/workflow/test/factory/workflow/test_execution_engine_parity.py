"""Parity tests proving Workflow execution engines stay provider-neutral."""
from __future__ import annotations

import hashlib
import sqlite3
import threading
import time

import pytest
from factory.workflow.runtime.canonical import canonical_json
from factory.workflow.runtime.envelope import Envelope
from factory.workflow.runtime.execution.adapters import create_executor
from factory.workflow.runtime.execution_engines import ExecutionEngineRegistry
from factory.workflow.runtime.models import Settings
from factory.workflow.runtime.operations import WorkflowError
from factory.workflow.runtime.runtime import WorkflowRuntime
from factory.workflow.runtime.storage.sqlite import SqliteWorkflowStorage

from .execution_engine_support import (
    DIGEST, ENGINES, BlockingInvoker, Invoker, enroll, event_values, runtime, spec,
)


@pytest.mark.parametrize("engine_id", ENGINES)
def test_engine_registration_snapshot_tuple_and_capability_parity(tmp_path, engine_id):
    invoker = Invoker(); owner = runtime(tmp_path, invoker); result = enroll(owner, engine_id)
    target, arguments, key, _ = invoker.calls[0]
    assert target.tool_name == f"execute_{engine_id}_attempt"
    assert target.brick_name == ("agent" if engine_id == "strands_graph" else "qa_fake")
    assert key == result["attempt_id"] and result["status"] == "succeeded"
    assert tuple(arguments[field] for field in (
        "workflow_run_id", "attempt_id", "revision", "engine_id", "registration_digest",
        "request_digest", "provider_request_digest",
    )) == (result["run_id"], result["attempt_id"], 1, engine_id,
          result["registration_digest"], result["request_digest"], DIGEST)
    snapshot = owner.durable_storage.load_workflow_version(owner.get_run(
        run_id=result["run_id"], envelope=Envelope())["workflow_version_id"])
    assert snapshot.steps[0].tool_target == target and snapshot.steps[0].service_binding == "execution"
    capabilities = owner.get_capabilities()["feature_flags"]["inhouse_execution_engines"]
    assert {item["engine_id"] for item in capabilities} == set(ENGINES)
    assert next(item for item in capabilities if item["engine_id"] == engine_id)["registration_digest"] == result["registration_digest"]


@pytest.mark.parametrize("engine_id", ENGINES)
def test_canonical_replay_and_every_frozen_change_conflicts(tmp_path, engine_id):
    owner = runtime(tmp_path, Invoker()); first = enroll(owner, engine_id)
    assert enroll(owner, engine_id)["run_id"] == first["run_id"]
    for name, value in (
        ("request", {"inline": {"provider": "other"}, "reference": None}),
        ("provider_request_digest", "b" * 64),
    ):
        kwargs = {"engine_id": engine_id, "request": {"inline": {"provider": engine_id}, "reference": None},
                  "provider_request_digest": DIGEST, "run_key": f"key-{engine_id}", "envelope": Envelope(tenant_id="tenant")}
        kwargs[name] = value
        with pytest.raises(WorkflowError, match="run-key conflict"):
            owner.enroll_execution(**kwargs)
    changed = runtime(tmp_path / "changed", Invoker(), specs=[spec(engine_id, provider="changed")])
    assert changed.get_capabilities()["feature_flags"]["inhouse_execution_engines"][0]["registration_digest"] != first["registration_digest"]


def test_missing_engine_fails_loudly(tmp_path):
    with pytest.raises(ValueError, match="unknown execution engine: missing"):
        enroll(runtime(tmp_path, Invoker()), "missing")


@pytest.mark.parametrize("engine_id", ENGINES)
def test_journal_cancellation_and_frozen_snapshot_parity(tmp_path, engine_id):
    invoker = BlockingInvoker(); owner = runtime(tmp_path, invoker)
    result, errors = {}, []
    thread = threading.Thread(target=lambda: _enroll(owner, engine_id, result, errors)); thread.start()
    assert invoker.started.wait(timeout=5)
    record = owner.durable_storage.get_run_by_key(run_key=f"key-{engine_id}")
    running = {**result} if result else {"run_id": record.run_id,
        "attempt_id": owner.durable_storage.list_task_attempts(run_id=record.run_id)[0]["attempt_id"],
        "registration_digest": spec(engine_id).registration_digest,
        "request_digest": hashlib.sha256(canonical_json({"inline":{"provider":engine_id},"reference":None}).encode()).hexdigest()}
    first, terminal = {"kind": engine_id, "n": 0}, {"kind": "done"}
    assert owner.append_execution_event(**event_values(owner, running, engine_id, 0, first))["appended"]
    assert not owner.append_execution_event(**event_values(owner, running, engine_id, 0, first))["appended"]
    assert owner.append_execution_event(**event_values(owner, running, engine_id, 1, terminal, True))["appended"]
    rows = owner.get_execution_events(workflow_run_id=record.run_id)
    assert [row["sequence"] for row in rows] == [0, 1] and rows[-1]["terminal"]
    cancelled = owner.cancel_run(run_id=record.run_id, reason="stop", envelope=Envelope(tenant_id="tenant"))
    assert cancelled["status"] == "cancelled"
    assert next(call for call in invoker.calls if call[0].tool_name.startswith("cancel_"))[1]["engine_id"] == engine_id
    invoker.release.set(); thread.join(timeout=5)
    assert not thread.is_alive() and not errors



class _Crash(BaseException):
    pass


class _CrashInvoker(Invoker):
    def invoke(self, **kwargs):
        if kwargs["target"].tool_name.startswith("execute_"):
            self.calls.append((kwargs["target"], kwargs["arguments"], kwargs["idempotency_key"], kwargs["envelope"]))
            raise _Crash("simulated process stop")
        return super().invoke(**kwargs)


@pytest.mark.parametrize("engine_id", ENGINES)
@pytest.mark.parametrize("live_specs", [[], [spec("strands_graph", provider="repointed")]])
def test_restart_uses_frozen_engine_when_live_registry_is_removed_or_repointed(tmp_path, engine_id, live_specs):
    crashing = _CrashInvoker(); owner = runtime(tmp_path, crashing)
    with pytest.raises(_Crash):
        enroll(owner, engine_id)
    record = owner.durable_storage.get_run_by_key(run_key=f"key-{engine_id}")
    before = owner.durable_storage.list_task_attempts(run_id=record.run_id)[0]
    with sqlite3.connect(tmp_path / "config" / "state.db") as conn:
        conn.execute("UPDATE task_attempts SET lease_expires_at=? WHERE attempt_id=?", ("1970-01-01T00:00:00+00:00", before["attempt_id"]))
    storage = SqliteWorkflowStorage(tmp_path / "config" / "state.db"); storage.init_schema()
    settings = Settings(); resumed_invoker = Invoker()
    restarted = WorkflowRuntime(config_dir=tmp_path / "config", settings=settings,
        settings_raw=settings.model_dump(), workflows=[], storage=storage, executor=create_executor(),
        tool_invoker=resumed_invoker, execution_engines=ExecutionEngineRegistry(live_specs))
    resumed = restarted.resume_run(run_id=record.run_id, envelope=Envelope(tenant_id="tenant"))
    assert resumed["status"] == "succeeded"
    assert resumed_invoker.calls[0][0] == crashing.calls[0][0]
    assert resumed_invoker.calls[0][1]["request"] == crashing.calls[0][1]["request"]
    assert resumed_invoker.calls[0][1]["registration_digest"] == crashing.calls[0][1]["registration_digest"]


def test_legacy_event_backfill_is_idempotent_and_preserves_generic_read_parity(tmp_path):
    invoker = BlockingInvoker(); owner = runtime(tmp_path, invoker)
    legacy_thread = threading.Thread(target=_enroll, args=(owner, "strands_graph", {}, [], "legacy")); legacy_thread.start()
    for _ in range(100):
        legacy_record = owner.durable_storage.get_run_by_key(run_key="legacy")
        if legacy_record is not None: break
        time.sleep(.01)
    assert legacy_record is not None; invoker.release.set(); legacy_thread.join(timeout=5)
    invoker.release = threading.Event(); mixed_owner = runtime(tmp_path, invoker)
    mixed_errors: list[BaseException] = []
    mixed_thread = threading.Thread(target=_enroll, args=(mixed_owner, "strands_graph", {}, mixed_errors, "mixed")); mixed_thread.start()
    for _ in range(100):
        mixed_record = mixed_owner.durable_storage.get_run_by_key(run_key="mixed")
        if mixed_record is not None: break
        if mixed_errors: raise mixed_errors[0]
        time.sleep(.01)
    assert mixed_record is not None
    records = [legacy_record, mixed_record]
    for _ in range(100):
        attempt_rows = [
            owner.durable_storage.list_task_attempts(run_id=record.run_id)
            for record in records
        ]
        if all(attempt_rows):
            break
        time.sleep(.01)
    assert all(attempt_rows)
    attempts = [rows[0] for rows in attempt_rows]
    legacy = (({"event": "legacy-0"}, False), ({"event": "legacy-final"}, True))
    mixed_legacy = {"event": "mixed-legacy"}
    with sqlite3.connect(tmp_path / "config" / "state.db") as conn:
        for sequence, (raw, terminal) in enumerate(legacy):
            encoded = canonical_json(raw); conn.execute("INSERT INTO managed_graph_events VALUES(?,?,?,?,?,?,?,?,?)", (attempts[0]["attempt_id"], attempts[0]["revision"], sequence, records[0].run_id, "m" * 64, hashlib.sha256(encoded.encode()).hexdigest(), terminal, encoded, f"2026-01-01T00:00:0{sequence}+00:00"))
        encoded = canonical_json(mixed_legacy); conn.execute("INSERT INTO managed_graph_events VALUES(?,?,?,?,?,?,?,?,?)", (attempts[1]["attempt_id"], attempts[1]["revision"], 0, records[1].run_id, "n" * 64, hashlib.sha256(encoded.encode()).hexdigest(), False, encoded, "2026-01-01T00:00:00+00:00"))
    owner.durable_storage.init_schema(); owner.durable_storage.init_schema()
    mixed = {"run_id": records[1].run_id, "attempt_id": attempts[1]["attempt_id"], "registration_digest": spec("strands_graph").registration_digest, "request_digest": hashlib.sha256(canonical_json({"inline":{"provider":"strands_graph"},"reference":None}).encode()).hexdigest()}
    mixed_owner.append_execution_event(**event_values(mixed_owner, mixed, "strands_graph", 1, {"event": "new-final"}, True))
    legacy_rows, mixed_rows = (owner.get_execution_events(workflow_run_id=record.run_id) for record in records)
    assert [(row["sequence"], row["terminal"], row["raw_digest"]) for row in legacy_rows] == [(i, terminal, hashlib.sha256(canonical_json(raw).encode()).hexdigest()) for i, (raw, terminal) in enumerate(legacy)]
    assert [row["sequence"] for row in mixed_rows] == [0, 1] and mixed_rows[-1]["terminal"]
    assert all(row["engine_id"] == "legacy-v1" and row["safe_metadata"] == {} for row in legacy_rows)
    assert mixed_rows[0]["engine_id"] == "legacy-v1" and mixed_rows[1]["engine_id"] == "strands_graph"
    invoker.release.set(); mixed_thread.join(timeout=5); assert not mixed_thread.is_alive()


def _enroll(owner, engine_id, result, errors, key=None):
    try: result.update(enroll(owner, engine_id, key=key))
    except BaseException as exc: errors.append(exc)
