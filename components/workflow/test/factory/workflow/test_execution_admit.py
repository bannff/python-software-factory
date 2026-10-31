from __future__ import annotations

from factory.workflow.runtime.envelope import Envelope

from .test_managed_graph import DIGEST, GraphInvoker, descriptor, runtime


def test_admit_only_persists_pending_attempt_without_provider_call(tmp_path) -> None:
    invoker = GraphInvoker()
    owner = runtime(tmp_path, invoker)
    admitted = owner.enroll_execution(
        engine_id="strands_graph", request=descriptor(),
        provider_request_digest=DIGEST, run_key="background-key",
        envelope=Envelope(tenant_id="tenant"), execute=False,
        launch_metadata={"kind": "test_admit", "origin_session_id": "s1"},
    )
    assert admitted["status"] == "running"
    persisted = owner.get_run(run_id=admitted["run_id"], envelope=Envelope())
    assert persisted["input"]["launch_metadata"] == {
        "kind": "test_admit", "origin_session_id": "s1",
    }
    assert admitted["attempt_id"].startswith("wfa:v1:")
    assert admitted["attempt_revision"] == 0
    assert invoker.calls == []
    attempts = owner.durable_storage.list_task_attempts(run_id=admitted["run_id"])
    assert [(item["status"], item["revision"]) for item in attempts] == [("pending", 0)]

    driven = owner.resume_run(run_id=admitted["run_id"], envelope=Envelope(tenant_id="tenant"))
    assert driven == {"ok": True, "status": "succeeded"}
    assert len(invoker.calls) == 1


def test_admit_only_replay_returns_same_run_and_attempt(tmp_path) -> None:
    owner = runtime(tmp_path, GraphInvoker())
    values = dict(engine_id="strands_graph", request=descriptor(),
                  provider_request_digest=DIGEST, run_key="same-key",
                  envelope=Envelope(tenant_id="tenant"), execute=False)
    first, replay = owner.enroll_execution(**values), owner.enroll_execution(**values)
    assert (replay["run_id"], replay["attempt_id"]) == (first["run_id"], first["attempt_id"])
