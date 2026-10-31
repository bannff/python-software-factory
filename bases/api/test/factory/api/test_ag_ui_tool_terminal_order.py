"""Regression: AG-UI tool lifecycle events must precede RUN_FINISHED."""
from __future__ import annotations

import json
import os
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _events(raw: str) -> list[dict]:
    return [
        json.loads(line[6:])
        for line in raw.splitlines()
        if line.startswith("data: ")
    ]


def _run(scripted) -> list[dict]:
    from factory.api.runtime.ag_ui_routes import register_ag_ui_routes

    app = FastAPI()
    register_ag_ui_routes(app)
    with patch.dict(os.environ, {"CHAT_STREAMING": "on"}, clear=False), patch(
        "factory.agent.interface.get_chat_agent_stream", new=scripted,
    ):
        response = TestClient(app).post("/ag-ui/run", json={
            "threadId": "ordering-thread",
            "runId": "ordering-run",
            "messages": [{"role": "user", "content": "open timeline"}],
        })
    return _events(response.text)


def test_frontend_tool_closes_before_run_finished_without_server_result() -> None:
    from factory.agent.runtime.models import DoneEvent, ToolCallDeltaEvent, ToolResultEvent

    async def scripted(thread_id, message, fe_tools=None, messages=None, agent_id=None):
        del thread_id, message, fe_tools, messages, agent_id
        yield ToolCallDeltaEvent(
            tool_call_id="fe-order-1", tool_name="fe_navigate_canvas",
            args_delta='{"view":"timeline-v2"}',
        )
        yield ToolResultEvent(tool_call_id="fe-order-1", payload={
            "_frontend_pending": True,
            "name": "fe_navigate_canvas",
            "args": {"view": "timeline-v2"},
        })
        yield DoneEvent(reason="stop")

    types = [event["type"] for event in _run(scripted)]
    assert types == [
        "RUN_STARTED", "TOOL_CALL_START", "TOOL_CALL_ARGS",
        "TOOL_CALL_END", "RUN_FINISHED",
    ]


def test_backend_tool_end_and_result_both_precede_run_finished() -> None:
    from factory.agent.runtime.models import DoneEvent, ToolCallDeltaEvent, ToolResultEvent

    async def scripted(thread_id, message, fe_tools=None, messages=None, agent_id=None):
        del thread_id, message, fe_tools, messages, agent_id
        yield ToolCallDeltaEvent(
            tool_call_id="backend-order-1", tool_name="ui_dispatch_action",
            args_delta='{"action":{}}',
        )
        yield ToolResultEvent(
            tool_call_id="backend-order-1",
            payload={"ok": True, "data": {"success": True}},
        )
        yield DoneEvent(reason="stop")

    types = [event["type"] for event in _run(scripted)]
    assert types == [
        "RUN_STARTED", "TOOL_CALL_START", "TOOL_CALL_ARGS",
        "TOOL_CALL_END", "TOOL_CALL_RESULT", "RUN_FINISHED",
    ]
