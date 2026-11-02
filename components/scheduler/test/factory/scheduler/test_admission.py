from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from factory.mcp_utils.interface import get_service, set_service
from factory.scheduler.mcp.admission import check_agent, check_fields

NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)


@pytest.mark.parametrize("task,kind,interval,at,code", [
    ("   ", "cron", None, None, "scheduler_task_required"),
    ("work", "interval", 15, None, "scheduler_interval_too_short"),
    ("work", "interval", None, None, "scheduler_interval_too_short"),
    ("work", "one_shot", None, NOW - timedelta(days=1), "scheduler_one_shot_in_past"),
])
def test_invalid_new_schedules_get_typed_codes(task, kind, interval, at, code) -> None:
    with pytest.raises(ValueError, match=code):
        check_fields(task, kind, interval, at, now=NOW)


def test_valid_new_schedules_pass() -> None:
    check_fields("work", "interval", 60, None, now=NOW)
    check_fields("work", "one_shot", None, NOW + timedelta(minutes=5), now=NOW)
    check_fields("work", "cron", None, None, now=NOW)


def _registry(ids):
    def factory(_caller):
        return lambda target, **kw: {"ok": True, "result": {"structured_content": {
            "ok": True, "data": {"count": len(ids), "agents": [{"id": i} for i in ids]}}}}
    return factory


def test_unknown_agent_is_rejected_and_known_agent_passes() -> None:
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", _registry(["developer"]))
    try:
        asyncio.run(check_agent("developer", {}))
        with pytest.raises(ValueError, match="scheduler_agent_not_found"):
            asyncio.run(check_agent("nope-agent", {}))
    finally:
        set_service("tool_invoker_for_caller", previous)


def test_without_an_agent_brick_the_agent_id_stays_opaque() -> None:
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", None)
    try:
        asyncio.run(check_agent("anything", {}))
    finally:
        set_service("tool_invoker_for_caller", previous)
