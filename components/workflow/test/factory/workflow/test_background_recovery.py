from __future__ import annotations

import pytest

from factory.workflow.runtime.background_recovery import schedule_background_recovery
from factory.workflow.runtime.envelope import Envelope

from .test_managed_graph import DIGEST, GraphInvoker, descriptor, runtime



@pytest.fixture(autouse=True)
def completion_transport():
    from factory.mcp_utils.interface import get_service, set_service

    previous = get_service("tool_invoker_for_caller")

    def factory(_caller):
        return lambda *args, **kwargs: {
            "ok": True,
            "result": {"structured_content": {"ok": True, "data": {}}},
        }

    set_service("tool_invoker_for_caller", factory)
    try:
        yield
    finally:
        set_service("tool_invoker_for_caller", previous)

@pytest.mark.asyncio
async def test_recovery_resumes_only_active_background_runs(tmp_path) -> None:
    invoker = GraphInvoker()
    owner = runtime(tmp_path, invoker)
    background = owner.enroll_execution(
        engine_id="strands_graph", request=descriptor("background"),
        provider_request_digest=DIGEST, run_key="background-key",
        envelope=Envelope(tenant_id="tenant", principal_id="owner"),
        execute=False,
        launch_metadata={"kind": "background_subagent", "origin_session_id": "s1"},
    )
    owner.enroll_execution(
        engine_id="strands_graph", request=descriptor("foreground"),
        provider_request_digest=DIGEST, run_key="foreground-key",
        envelope=Envelope(tenant_id="tenant", principal_id="owner"),
        execute=False, launch_metadata={"kind": "registered_graph"},
    )
    scheduled = []
    assert schedule_background_recovery(owner, scheduled.append) == (background["run_id"],)
    assert invoker.calls == []
    await scheduled[0]
    assert len(invoker.calls) == 1
    assert owner.get_run(
        run_id=background["run_id"], envelope=Envelope(tenant_id="tenant"),
    )["status"] == "succeeded"

    replay = []
    assert schedule_background_recovery(owner, replay.append) == ()
    assert replay == []


@pytest.mark.asyncio
async def test_concurrent_recovery_is_fenced_by_durable_attempt_claim(tmp_path) -> None:
    invoker = GraphInvoker()
    owner = runtime(tmp_path, invoker)
    admitted = owner.enroll_execution(
        engine_id="strands_graph", request=descriptor(),
        provider_request_digest=DIGEST, run_key="race-key",
        envelope=Envelope(tenant_id="tenant"), execute=False,
        launch_metadata={"kind": "background_subagent", "origin_session_id": "s1"},
    )
    scheduled = []
    schedule_background_recovery(owner, scheduled.append)
    schedule_background_recovery(owner, scheduled.append)
    assert len(scheduled) == 2
    await scheduled[0]
    await scheduled[1]
    assert len(invoker.calls) == 1
    assert owner.get_run(run_id=admitted["run_id"], envelope=Envelope())["status"] == "succeeded"


@pytest.mark.asyncio
async def test_fresh_runtime_reconciles_persisted_background_run(tmp_path) -> None:
    from factory.workflow.runtime.execution.adapters import create_executor
    from factory.workflow.runtime.models import Settings
    from factory.workflow.runtime.runtime import WorkflowRuntime
    from factory.workflow.runtime.storage.sqlite import SqliteWorkflowStorage

    first_invoker = GraphInvoker()
    first = runtime(tmp_path, first_invoker)
    admitted = first.enroll_execution(
        engine_id="strands_graph", request=descriptor(),
        provider_request_digest=DIGEST, run_key="restart-key",
        envelope=Envelope(tenant_id="tenant"), execute=False,
        launch_metadata={"kind": "background_subagent", "origin_session_id": "s1"},
    )
    storage = SqliteWorkflowStorage(first.config_dir / "state.db")
    storage.init_schema()
    settings = Settings()
    resumed_invoker = GraphInvoker()
    second = WorkflowRuntime(
        config_dir=first.config_dir, settings=settings,
        settings_raw=settings.model_dump(), workflows=[], storage=storage,
        executor=create_executor(), tool_invoker=resumed_invoker,
        execution_engines=first.execution_engines,
    )
    scheduled = []
    assert schedule_background_recovery(second, scheduled.append) == (admitted["run_id"],)
    await scheduled[0]
    assert len(resumed_invoker.calls) == 1
    assert second.get_run(run_id=admitted["run_id"], envelope=Envelope())["status"] == "succeeded"
