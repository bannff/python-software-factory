"""Provider-neutral retry and cancellation fencing regression tests."""
from __future__ import annotations

import threading

import pytest
from factory.workflow.runtime.envelope import Envelope

from .execution_engine_support import ENGINES, Invoker, enroll, runtime


class RetryBlockingInvoker(Invoker):
    def __init__(self) -> None:
        super().__init__()
        self.executions = 0
        self.started = threading.Event()
        self.release = threading.Event()

    def invoke(self, **kwargs):
        if kwargs["target"].tool_name.startswith("cancel_"):
            return super().invoke(**kwargs)
        self.executions += 1
        if self.executions == 1:
            self.calls.append((kwargs["target"], kwargs["arguments"],
                               kwargs["idempotency_key"], kwargs["envelope"]))
            self.bindings.append(kwargs["attempt"])
            return {"ok": True, "result": {"kind": "tool", "content": [], "meta": {},
                "structured_content": {"schema_version": "v1", "ok": True,
                "data": {"status": "failed", "retryable": True, "error": "retry"},
                "error": None, "idempotency_key": None}}}
        self.started.set()
        assert self.release.wait(timeout=5)
        return super().invoke(**kwargs)


@pytest.mark.parametrize("engine_id", ENGINES)
def test_retry_then_cancel_signals_only_active_tuple_and_fences_old_events(
    tmp_path, engine_id,
) -> None:
    invoker = RetryBlockingInvoker()
    owner = runtime(tmp_path, invoker)
    result: dict = {}
    errors: list[BaseException] = []
    thread = threading.Thread(target=_enroll, args=(owner, engine_id, result, errors))
    thread.start()
    assert invoker.started.wait(timeout=5)
    attempts = owner.durable_storage.list_task_attempts(
        run_id=owner.durable_storage.get_run_by_key(run_key=f"key-{engine_id}").run_id
    )
    assert len(attempts) == 2
    old, active = attempts
    cancelled = owner.cancel_run(
        run_id=owner.durable_storage.get_run_by_key(run_key=f"key-{engine_id}").run_id,
        reason="stop", envelope=Envelope(tenant_id="tenant"),
    )
    cancel = [call for call in invoker.calls if call[0].tool_name.startswith("cancel_")]
    assert cancelled["status"] == "cancelled" and len(cancel) == 1
    assert cancel[0][1]["attempt_id"] == active["attempt_id"]
    assert cancel[0][1]["revision"] == 1
    assert old["attempt_id"] != cancel[0][1]["attempt_id"]
    for binding in (invoker.bindings[0], invoker.bindings[1]):
        with pytest.raises(ValueError, match="stale|terminal"):
            owner.append_execution_event(
                **binding, sequence=0, terminal=False,
                raw_evidence={"late": binding["attempt_id"]},
                safe_metadata={"provider": engine_id},
            )
    invoker.release.set()
    thread.join(timeout=5)
    assert not thread.is_alive() and not errors and result["status"] == "cancelled"


def _enroll(owner, engine_id, result, errors) -> None:
    try:
        result.update(enroll(owner, engine_id))
    except BaseException as exc:
        errors.append(exc)
