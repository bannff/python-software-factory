from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pytest

from factory.mcp_utils.interface import (
    get_service, project_envelope_arguments, set_service,
)
from factory.scheduler.mcp.contracts import AddScheduleInput
from factory.scheduler.runtime.adapters.sql import SQLScheduleStore
from factory.scheduler.runtime.fire_dispatch import replay_claimed
from factory.scheduler.runtime.lifecycle import SchedulerLifecycle
from factory.storage.interface import StorageRuntime
from factory.workflow.runtime.envelope import Envelope, FrozenEnvelope
from factory.workflow.runtime.loop_admission import admit_pending
from factory.workflow.runtime.loop_lifecycle import LoopLifecycle
from factory.workflow.runtime.loop_models import LoopKind, LoopRecord, LoopState
from factory.workflow.runtime.loop_reconcile import reconcile_cycles
from factory.workflow.runtime.storage.sqlite import SqliteWorkflowStorage


def _workflow(path: Path) -> SqliteWorkflowStorage:
    store = SqliteWorkflowStorage(path)
    store.init_schema()
    return store


def _scheduler(path: Path) -> SchedulerLifecycle:
    sql = StorageRuntime().get_sql_store("sqlite", db_path=str(path))
    return SchedulerLifecycle(SQLScheduleStore(sql))


def _loop(root: Path, kind: LoopKind = LoopKind.GOAL) -> LoopRecord:
    now = datetime.now(timezone.utc)
    return LoopRecord(
        tenant_id="tenant", owner_id="owner", loop_id="acceptance",
        origin_session_id="session", origin_thread_id="thread",
        agent_id="developer", kind=kind, objective="advance three cycles",
        cycle_instructions="return continue twice then success",
        interval_seconds=60, max_cycles=3, project_root=str(root),
        project_root_digest=hashlib.sha256(str(root).encode()).hexdigest(),
        created_at=now, updated_at=now,
        initiation_envelope=FrozenEnvelope(
            tenant_id="tenant", principal_id="owner", session_id="thread",
        ),
    )


def _ok(data: dict) -> dict:
    return {"ok": True, "result": {"structured_content": {
        "ok": True, "data": data,
    }}}


def _add_handler() -> None:
    """Stand-in exposing the real strict ``scheduler_add`` ingress model."""
_add_handler._mcp_input_model = AddScheduleInput


def _router(refs: dict, dispositions: list[str]):
    def factory(_caller):
        def invoke(target, **kwargs):
            args = kwargs["arguments"]
            brick, tool = target["brick_name"], target["tool_name"]
            if brick == "scheduler" and tool == "scheduler_add":
                loop = refs["loop"]
                projected = project_envelope_arguments(
                    _add_handler, args, kwargs["envelope"],
                )
                wire = AddScheduleInput.model_validate(projected)
                record = refs["scheduler"].create(
                    loop.tenant_id, loop.owner_id, loop.origin_session_id,
                    loop.origin_thread_id, wire.agent_id, wire.task,
                    wire.kind, one_shot_at=wire.one_shot_at,
                    output_schema=wire.output_schema,
                    delivery_mode=wire.delivery_mode, loop_id=wire.loop_id,
                    loop_cycle=wire.loop_cycle, schedule_id=wire.schedule_id,
                )
                return _ok({"schedule": record.model_dump(mode="json")})
            if brick == "scheduler" and tool == "scheduler_get_fire":
                fire = refs["scheduler"].store.get_fire(
                    "tenant", "owner", args["schedule_id"], args["fire_sequence"],
                )
                return _ok({"fire": fire.model_dump(mode="json")}) if fire else _ok({})
            if brick == "agent" and tool == "spawn_background":
                cycle = int(args["loop_cycle"])
                run_id = f"child-{cycle}"
                store = refs["workflow"]
                run = store.get_run(run_id=run_id)
                envelope = Envelope.model_validate(kwargs["envelope"])
                if run is None:
                    run = store.create_run(
                        run_id=run_id, run_key=args["launch_id"],
                        workflow_id="loop-child", workflow_version=1,
                        tenant_id="tenant", input={"launch_metadata": {
                            "kind": "workflow_loop_cycle", "loop_id": "acceptance",
                            "loop_cycle": str(cycle),
                        }}, envelope=envelope, now=datetime.now(timezone.utc),
                    )
                    report = {
                        "disposition": dispositions[cycle - 1],
                        "summary": f"cycle {cycle}", "blocker": None,
                        "evidence": [f"cycle-{cycle}"],
                    }
                    store.update_run(
                        run_id=run_id, status="succeeded", current_step_id=None,
                        waiting_for_event_type=None, last_event_id=None,
                        result={"task_result": {"result": {
                            "structured_outputs": {"developer": report},
                        }}}, error=None, now=datetime.now(timezone.utc),
                    )
                return _ok({"run_id": run_id, "status": "running"})
            if brick in {"events", "notification"}:
                return _ok({"accepted": True})
            raise AssertionError((brick, tool))
        return invoke
    return factory


async def _cycle(refs: dict, root: Path) -> None:
    await admit_pending(refs["workflow"], root)
    cycle_number = refs["loop"].next_cycle
    cycle = refs["workflow"].get_cycle(
        "tenant", "owner", "acceptance", cycle_number,
    )
    schedule = refs["scheduler"].get("tenant", "owner", cycle.schedule_id)
    refs["scheduler"].claim(schedule, cycle.scheduled_for)
    await replay_claimed(refs["scheduler"])
    await reconcile_cycles(refs["workflow"], root)


@pytest.mark.asyncio
async def test_three_cycle_goal_survives_restart_and_halts_successfully(tmp_path) -> None:
    workflow_path, scheduler_path = tmp_path / "workflow.db", tmp_path / "scheduler.db"
    refs = {
        "workflow": _workflow(workflow_path),
        "scheduler": _scheduler(scheduler_path),
        "loop": _loop(tmp_path),
    }
    LoopLifecycle(refs["workflow"]).start(refs["loop"])
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", _router(refs, ["continue", "continue", "success"]))
    try:
        for expected in range(1, 4):
            refs["loop"] = refs["workflow"].get_loop("tenant", "owner", "acceptance")
            await _cycle(refs, tmp_path)
            refs["workflow"] = _workflow(workflow_path)
            refs["scheduler"] = _scheduler(scheduler_path)
            loop = refs["workflow"].get_loop("tenant", "owner", "acceptance")
            assert loop.last_settled_cycle == expected
        assert loop.state is LoopState.SUCCEEDED
        assert loop.terminal_reason == "goal_complete"
        assert refs["workflow"].get_cycle("tenant", "owner", "acceptance", 4) is None
    finally:
        set_service("tool_invoker_for_caller", previous)


@pytest.mark.asyncio
async def test_restart_then_stop_file_prevents_second_cycle(tmp_path) -> None:
    refs = {"workflow": _workflow(tmp_path / "w.db"),
            "scheduler": _scheduler(tmp_path / "s.db"), "loop": _loop(tmp_path)}
    LoopLifecycle(refs["workflow"]).start(refs["loop"])
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", _router(refs, ["continue", "success"]))
    try:
        await _cycle(refs, tmp_path)
        (tmp_path / ".companion-loop-stop-acceptance").touch()
        refs["workflow"] = _workflow(tmp_path / "w.db")
        refs["scheduler"] = _scheduler(tmp_path / "s.db")
        assert await admit_pending(refs["workflow"], tmp_path) == ()
        loop = refs["workflow"].get_loop("tenant", "owner", "acceptance")
        assert loop.state is LoopState.STOPPED
        assert refs["scheduler"].store.get("tenant", "owner", "loop_acceptance_2") is None
    finally:
        set_service("tool_invoker_for_caller", previous)


@pytest.mark.asyncio
async def test_monitor_no_change_continues_without_false_success(tmp_path) -> None:
    loop = _loop(tmp_path, LoopKind.MONITOR).model_copy(update={"max_cycles": 2})
    refs = {"workflow": _workflow(tmp_path / "monitor-w.db"),
            "scheduler": _scheduler(tmp_path / "monitor-s.db"), "loop": loop}
    LoopLifecycle(refs["workflow"]).start(loop)
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", _router(refs, ["continue", "success"]))
    try:
        await _cycle(refs, tmp_path)
        current = refs["workflow"].get_loop("tenant", "owner", "acceptance")
        assert current.kind is LoopKind.MONITOR
        assert current.state is LoopState.ACTIVE
        assert current.last_settled_cycle == 1
        assert refs["workflow"].get_cycle(
            "tenant", "owner", "acceptance", 2,
        ) is not None
    finally:
        set_service("tool_invoker_for_caller", previous)
