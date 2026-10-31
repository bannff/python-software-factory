from __future__ import annotations

from types import SimpleNamespace

import pytest

from factory.agent.runtime.background import launch as module
from factory.mcp_utils.interface import (
    get_service, reset_envelope, set_envelope, set_service,
)


class Registry:
    def get(self, agent_id: str):
        return object() if agent_id == "worker" else None


@pytest.mark.asyncio
async def test_background_launch_admits_then_defers_drive(monkeypatch) -> None:
    admitted = SimpleNamespace(
        run_id="run-1", run_key="launch-1", status="running",
    )
    captured, calls = [], []

    async def managed(config, task, context, **kwargs):
        assert config.nodes[0].agent_id == "worker"
        assert task == "do bounded work"
        assert context["origin_session_id"] == "session-1"
        assert kwargs["execute"] is False
        metadata = kwargs["launch_metadata"]
        assert metadata["kind"] == "background_subagent"
        assert metadata["origin_session_id"] == "session-1"
        assert metadata["background_session_id"] == "background-session-1"
        assert metadata["background_thread_id"].startswith("bg_")
        assert metadata["persona_id"] == "worker"
        return admitted

    def factory(_caller):
        def invoke(target, **kwargs):
            calls.append((target, kwargs))
            if target["brick_name"] == "session":
                if target["tool_name"] == "resolve_thread":
                    data = {"session": {
                        "session_id": "session-1", "thread_id": "thread-1",
                    }}
                else:
                    data = {"session": {
                        "session_id": "background-session-1",
                        "thread_id": kwargs["arguments"]["thread_id"],
                    }}
            else:
                data = {"ok": True, "status": "succeeded"}
            return {"ok": True, "result": {"structured_content": {
                "ok": True, "data": data,
            }}}
        return invoke

    monkeypatch.setattr(module, "launch_managed_graph", managed)
    previous_invoker = get_service("tool_invoker_for_caller")
    previous_launcher = get_service("background_task_launcher")
    set_service("tool_invoker_for_caller", factory)
    set_service("background_task_launcher", captured.append)
    token = set_envelope({
        "tenant_id": "tenant-1", "principal_id": "owner-1",
        "thread_id": "thread-1",
    })
    try:
        result = await module.launch_background(
            Registry(), "worker", "do bounded work", "launch-1",
        )
        assert result == {
            "run_id": "run-1", "run_key": "launch-1", "status": "running",
            "agent_id": "worker", "origin_session_id": "session-1",
        }
        assert len(captured) == 1
        assert [call[0]["brick_name"] for call in calls] == ["session", "session"]
        await captured[0]
        assert [call[0]["brick_name"] for call in calls] == [
            "session", "session", "workflow",
        ]
    finally:
        reset_envelope(token)
        set_service("tool_invoker_for_caller", previous_invoker)
        set_service("background_task_launcher", previous_launcher)


@pytest.mark.asyncio
async def test_background_launch_rejects_unknown_persona() -> None:
    with pytest.raises(module.BackgroundLaunchError) as error:
        await module.launch_background(Registry(), "missing", "task", None)
    assert error.value.code == "unknown_agent_id"


@pytest.mark.asyncio
async def test_loop_cycle_launch_freezes_schema_and_internal_delivery(monkeypatch) -> None:
    captured = {}

    async def managed(config, task, context, **kwargs):
        captured["schema"] = config.nodes[0].output_schema
        captured["metadata"] = kwargs["launch_metadata"]
        return SimpleNamespace(run_id="run-loop", run_key="loop-key", status="running")

    def factory(_caller):
        def invoke(target, **kwargs):
            if target["tool_name"] == "resolve_thread":
                data = {"session": {"session_id": "origin", "thread_id": "thread"}}
            elif target["tool_name"] == "ensure_thread":
                data = {"session": {"session_id": "child", "thread_id": "bg"}}
            else:
                data = {"status": "succeeded"}
            return {"ok": True, "result": {"structured_content": {
                "ok": True, "data": data,
            }}}
        return invoke

    monkeypatch.setattr(module, "launch_managed_graph", managed)
    previous_invoker = get_service("tool_invoker_for_caller")
    previous_launcher = get_service("background_task_launcher")
    set_service("tool_invoker_for_caller", factory)
    pending = []
    set_service("background_task_launcher", pending.append)
    token = set_envelope({
        "tenant_id": "tenant", "principal_id": "owner", "thread_id": "thread",
    })
    try:
        await module.launch_background(
            Registry(), "worker", "cycle", "loop-key", None,
            "loop-cycle-report-v1", "workflow_loop", "goal_1", 2,
        )
        assert captured["schema"] == "loop-cycle-report-v1"
        assert captured["metadata"]["kind"] == "workflow_loop_cycle"
        assert captured["metadata"]["loop_id"] == "goal_1"
        assert captured["metadata"]["loop_cycle"] == "2"
        await pending[0]
    finally:
        reset_envelope(token)
        set_service("tool_invoker_for_caller", previous_invoker)
        set_service("background_task_launcher", previous_launcher)
