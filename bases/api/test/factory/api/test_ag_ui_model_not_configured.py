"""Legacy AG-UI path: model_not_configured becomes RUN_ERROR with a code (#239)."""
from __future__ import annotations

import json

import pytest

from factory.api.runtime.ag_ui_run_paths import RunPathOutcome, legacy_agent_reason


async def _collect(result: dict, outcome: RunPathOutcome) -> list[dict]:
    async def call_tool(name, args):
        return result

    def sse(evt):
        return evt

    events = []
    async for evt in legacy_agent_reason(
        "t", "r", "hello", call_tool, sse, lambda *_: {}, outcome=outcome,
    ):
        events.append(evt)
    return events


@pytest.mark.asyncio
async def test_model_not_configured_emits_coded_run_error() -> None:
    outcome = RunPathOutcome()
    events = await _collect({"ok": False, "error": "model_not_configured"}, outcome)
    assert [e["type"] for e in events] == ["RUN_ERROR"]
    assert events[0]["code"] == "model_not_configured"
    assert "COMPANION_X_CHAT_MODEL" in events[0]["message"]
    assert outcome.errored is True


@pytest.mark.asyncio
async def test_other_failures_keep_the_generic_text() -> None:
    outcome = RunPathOutcome()
    events = await _collect({"ok": False, "error": "tool_execution_failed"}, outcome)
    assert events[0]["type"] == "TEXT_MESSAGE_START"
    assert outcome.errored is False
