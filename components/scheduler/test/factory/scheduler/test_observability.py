from types import SimpleNamespace

import pytest

from factory.mcp_utils.interface import set_service
from factory.scheduler.runtime.observability import project_outcome


def _schedule():
    return SimpleNamespace(
        tenant_id="tenant", owner_id="owner", schedule_id="nightly",
        origin_thread_id="thread",
    )


def _fire():
    return SimpleNamespace(
        fire_sequence=5, launch_id="sched_nightly_5",
        workflow_run_id="run-5",
    )


@pytest.mark.asyncio
async def test_outcome_event_uses_owner_envelope_without_task_content() -> None:
    calls = []
    set_service("tool_invoker_for_caller", lambda caller: lambda target, **kwargs:
                calls.append((caller, target, kwargs)) or {"ok": True})
    await project_outcome(_schedule(), _fire(), "succeeded", False)
    assert len(calls) == 1
    caller, target, call = calls[0]
    assert caller == "scheduler"
    assert target == {"brick_name": "events", "tool_name": "events_publish"}
    assert call["envelope"]["principal_id"] == "owner"
    assert call["arguments"]["event_type"] == "scheduler.fire.succeeded"
    assert "task" not in call["arguments"]["payload"]


@pytest.mark.asyncio
async def test_auto_pause_projects_bound_inbox_publish_after_durable_outcome() -> None:
    calls = []
    set_service("tool_invoker_for_caller", lambda caller: lambda target, **kwargs:
                calls.append((target, kwargs)) or {"ok": True})
    await project_outcome(_schedule(), _fire(), "failed", True)
    assert [target["brick_name"] for target, _ in calls] == ["events", "notification"]
    target, call = calls[1]
    # Exact protected target + tool, not the public send_notification path.
    assert target == {"brick_name": "notification", "tool_name": "inbox_publish"}
    args = call["arguments"]
    assert args["event_type"] == "scheduler.schedule.auto_paused"
    assert args["subject_id"] == "nightly"          # target == schedule id
    assert args["revision"] == 5                     # fire_sequence
    assert args["title"] == "Schedule auto-paused"
    assert args["dedupe_key"] == "scheduler-auto-pause:nightly:5"
    assert call["idempotency_key"] == "scheduler-auto-pause:nightly:5"
    # A complete six-field projection binding is supplied to the caller rail.
    binding = call["projection"]
    assert set(binding) == {
        "tenant_id", "owner_id", "event_type", "subject_id", "revision",
        "payload_digest",
    }
    assert binding["tenant_id"] == "tenant" and binding["owner_id"] == "owner"
    # payload_digest binds the exact content the tool will recompute.
    assert args["payload_digest"] == binding["payload_digest"]
    assert len(binding["payload_digest"]) == 64


@pytest.mark.asyncio
async def test_observability_failure_never_blocks_scheduler_truth() -> None:
    def fail(*args, **kwargs):
        raise RuntimeError("events unavailable")
    set_service("tool_invoker_for_caller", lambda caller: fail)
    await project_outcome(_schedule(), _fire(), "failed", True)
