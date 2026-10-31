"""Integration tests for AG-UI SSE endpoint — POST /ag-ui/run."""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch


def _parse_sse(raw: str) -> list[dict]:
    """Parse SSE text into list of event dicts."""
    events = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def _make_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from starlette.middleware.cors import CORSMiddleware
    from factory.mcp_utils.interface import cors_options
    from factory.api.runtime.ag_ui_routes import register_ag_ui_routes

    app = FastAPI()
    app.add_middleware(CORSMiddleware, **cors_options())
    register_ag_ui_routes(app)
    return TestClient(app)
def _mock_call_tool(**overrides):
    """Create an async mock for _call_tool that returns sensible defaults."""
    agent_result = overrides.get("agent_result", {"text": "Hello from agent"})

    async def fake_call(tool_name: str, arguments: dict):
        if tool_name == "agent_reason":
            return agent_result
        return None

    return fake_call


class TestAGUIRunEndpoint:
    """POST /ag-ui/run → SSE stream with lifecycle events."""

    def test_agent_reason_receives_thread_id_in_context(self):
        seen: dict[str, object] = {}

        async def capture_call(tool_name: str, arguments: dict):
            if tool_name == "agent_reason":
                seen.update(arguments)
                return {"text": "ok"}
            return None

        with patch("factory.api.runtime.ag_ui_routes._call_tool",
                   side_effect=capture_call):
            client = _make_client()
            resp = client.post("/ag-ui/run", content=json.dumps({
                "threadId": "my-thread",
                "messages": [{"role": "user", "content": "x"}],
            }))

        assert resp.status_code == 200
        assert seen["task"] == "x"
        context = seen["context"]
        assert context["thread_id"] == "my-thread"
        assert context["chat_run_id"] == "my-thread"
        assert context["correlation_id"] == "my-thread"
        assert "run_id" not in context
        assert "workflow_run_id" not in context

    def test_ag_ui_sets_correlation_context_for_chat_runs(self):
        async def fake_call(tool_name: str, arguments: dict):
            if tool_name == "agent_reason":
                return {"text": "ok"}
            return None

        with patch("factory.api.runtime.ag_ui_routes._call_tool",
                   side_effect=fake_call), \
             patch("factory.mcp_utils.interface.push_envelope_updates") as mock_push, \
             patch("factory.mcp_server.interface.set_workflow_run_id") as mock_set_workflow_run_id:
            client = _make_client()
            resp = client.post("/ag-ui/run", content=json.dumps({
                "threadId": "thread-42",
                "runId": "run-42",
                "messages": [{"role": "user", "content": "x"}],
            }))

        assert resp.status_code == 200
        mock_push.assert_called_once_with(
            session_id="thread-42", correlation_id="run-42",
        )
        mock_set_workflow_run_id.assert_not_called()

    def test_ag_ui_sets_caller_hint_for_chat_runs(self):
        """The chat caller hint is available during, then removed after, a run."""
        seen: list[str | None] = []

        async def fake_call(tool_name: str, arguments: dict):
            if tool_name == "agent_reason":
                from factory.mcp_utils.interface import get_caller_hint

                seen.append(get_caller_hint())
                return {"text": "ok"}
            return None

        with patch("factory.api.runtime.ag_ui_routes._call_tool",
                   side_effect=fake_call):
            client = _make_client()
            resp = client.post("/ag-ui/run", content=json.dumps({
                "threadId": "thread-abcdef1234567890",
                "runId": "run-77",
                "messages": [{"role": "user", "content": "x"}],
            }))

        assert resp.status_code == 200
        assert seen == ["chat:thread-a"]
        from factory.mcp_utils.interface import get_caller_hint
        assert get_caller_hint() is None

    def test_ag_ui_materializes_tool_invocation_without_workflow_authority(self):
        from factory.mcp_server.runtime import graph_sink

        captured: list[dict[str, object]] = []
        queue_mock = MagicMock()
        queue_mock.put.side_effect = lambda fn: fn()

        async def fake_call(tool_name: str, arguments: dict):
            if tool_name == "agent_reason":
                graph_sink.materialize(
                    "agent",
                    "agent_reason",
                    success=True,
                    latency_ms=12.5,
                    caller="ag_ui",
                )
                return {"text": "ok"}
            return None

        prior_runtime = graph_sink._graph_runtime
        graph_sink._graph_runtime = {"sentinel": True}
        try:
            with patch.dict(os.environ, {"TELEMETRY_GRAPH_SINK": "true"}, clear=False), \
                 patch("factory.api.runtime.ag_ui_routes._call_tool", side_effect=fake_call), \
                 patch.object(graph_sink, "_ensure_drain_thread"), \
                 patch.object(graph_sink, "_SINK_QUEUE", queue_mock), \
                 patch.object(graph_sink, "_call_graph", side_effect=lambda *args, **kwargs: captured.append(kwargs)):
                client = _make_client()
                resp = client.post("/ag-ui/run", content=json.dumps({
                    "threadId": "thread-99",
                    "runId": "run-99",
                    "messages": [{"role": "user", "content": "x"}],
                }))
                _ = resp.text

            assert resp.status_code == 200
            tool_invocation = next(
                item for item in captured if item.get("entity_type") == "ToolInvocation"
            )
            session = next(
                item for item in captured if item.get("entity_type") == "Session"
            )
            relation = next(
                item for item in captured if item.get("relationship_type") == "CONTAINS_INVOCATION"
            )

            assert tool_invocation["properties"]["session_id"] == "thread-99"
            assert tool_invocation["properties"]["workflow_run_id"] is None
            assert tool_invocation["properties"]["caller"] == "ag_ui"
            assert session["entity_id"] == "session-thread-99"
            assert relation["source_id"] == "session-thread-99"
            assert relation["target_id"] == tool_invocation["entity_id"]
        finally:
            graph_sink._graph_runtime = prior_runtime

    def test_basic_run_lifecycle(self):
        with patch("factory.api.runtime.ag_ui_routes._call_tool",
                   side_effect=_mock_call_tool()):
            client = _make_client()
            resp = client.post("/ag-ui/run", content=json.dumps({
                "messages": [{"role": "user", "content": "hi"}],
            }))
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        events = _parse_sse(resp.text)
        types = [e["type"] for e in events]
        assert types[0] == "RUN_STARTED"
        assert types[-1] == "RUN_FINISHED"
        assert "TEXT_MESSAGE_START" in types
        assert "TEXT_MESSAGE_CONTENT" in types
        assert "TEXT_MESSAGE_END" in types

    def test_text_content_matches(self):
        with patch("factory.api.runtime.ag_ui_routes._call_tool",
                   side_effect=_mock_call_tool(agent_result={"text": "world"})):
            client = _make_client()
            resp = client.post("/ag-ui/run", content=json.dumps({
                "messages": [{"role": "user", "content": "hello"}],
            }))
        events = _parse_sse(resp.text)
        content_evts = [e for e in events if e["type"] == "TEXT_MESSAGE_CONTENT"]
        # Streaming may produce N deltas — assert the concatenation matches
        # rather than pinning a count, so this test passes whether the
        # legacy path (single delta) or the streaming path runs.
        assert len(content_evts) >= 1
        assert "".join(e["delta"] for e in content_evts) == "world"

    def test_thread_id_propagated(self):
        with patch("factory.api.runtime.ag_ui_routes._call_tool",
                   side_effect=_mock_call_tool()):
            client = _make_client()
            resp = client.post("/ag-ui/run", content=json.dumps({
                "threadId": "my-thread",
                "messages": [{"role": "user", "content": "x"}],
            }))
        events = _parse_sse(resp.text)
        started = events[0]
        assert started["threadId"] == "my-thread"

    def test_state_snapshot_emitted(self):
        with patch("factory.api.runtime.ag_ui_routes._call_tool",
                   side_effect=_mock_call_tool()):
            client = _make_client()
            resp = client.post("/ag-ui/run", content=json.dumps({
                "state": {"counter": 1},
                "messages": [{"role": "user", "content": "x"}],
            }))
        events = _parse_sse(resp.text)
        snap = [e for e in events if e["type"] == "STATE_SNAPSHOT"]
        assert len(snap) == 1
        assert snap[0]["snapshot"] == {"counter": 1}

    def test_no_state_no_snapshot(self):
        with patch("factory.api.runtime.ag_ui_routes._call_tool",
                   side_effect=_mock_call_tool()):
            client = _make_client()
            resp = client.post("/ag-ui/run", content=json.dumps({
                "messages": [{"role": "user", "content": "x"}],
            }))
        events = _parse_sse(resp.text)
        assert not any(e["type"] == "STATE_SNAPSHOT" for e in events)

    def test_empty_messages_still_runs(self):
        with patch("factory.api.runtime.ag_ui_routes._call_tool",
                   side_effect=_mock_call_tool()):
            client = _make_client()
            resp = client.post("/ag-ui/run", content=json.dumps({}))
        events = _parse_sse(resp.text)
        assert events[0]["type"] == "RUN_STARTED"
        assert events[-1]["type"] == "RUN_FINISHED"

    def test_invalid_json_returns_400(self):
        client = _make_client()
        resp = client.post("/ag-ui/run", content=b"not-json")
        assert resp.status_code == 400

    def test_agent_error_emits_run_error(self):
        async def failing_call(tool_name, arguments):
            if tool_name == "agent_reason":
                raise RuntimeError("LLM timeout")
            return None

        with patch("factory.api.runtime.ag_ui_routes._call_tool",
                   side_effect=failing_call):
            client = _make_client()
            resp = client.post("/ag-ui/run", content=json.dumps({
                "messages": [{"role": "user", "content": "x"}],
            }))
        events = _parse_sse(resp.text)
        types = [e["type"] for e in events]
        assert "RUN_ERROR" in types
        err = [e for e in events if e["type"] == "RUN_ERROR"][0]
        # Raw exception text must never leak into a user-visible message
        # (bd:python-factory-46338 / gh-750) — only a stable, redacted
        # string, with the real exception logged server-side.
        assert err["message"] == "Chat is temporarily unavailable. Please retry."
        assert "LLM timeout" not in err["message"]

    def test_cors_headers_present(self):
        with patch("factory.api.runtime.ag_ui_routes._call_tool",
                   side_effect=_mock_call_tool()):
            client = _make_client()
            resp = client.post("/ag-ui/run",
                               headers={"Origin": "http://localhost:3000"},
                               content=json.dumps({
                "messages": [{"role": "user", "content": "x"}],
            }))
        # CORSMiddleware echoes the allowed origin (allowlist, not "*").
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_options_preflight(self):
        client = _make_client()
        resp = client.options("/ag-ui/run", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        })
        # Starlette CORSMiddleware answers the preflight with 200.
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_cors_disallowed_origin_gets_no_acao(self):
        """Allowlist canary: an origin outside the list gets no ACAO header."""
        client = _make_client()
        resp = client.options("/ag-ui/run", headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "POST",
        })
        assert resp.headers.get("access-control-allow-origin") is None

    def test_message_ids_consistent(self):
        with patch("factory.api.runtime.ag_ui_routes._call_tool",
                   side_effect=_mock_call_tool()):
            client = _make_client()
            resp = client.post("/ag-ui/run", content=json.dumps({
                "messages": [{"role": "user", "content": "x"}],
            }))
        events = _parse_sse(resp.text)
        text_evts = [e for e in events if e["type"].startswith("TEXT_MESSAGE")]
        ids = {e["messageId"] for e in text_evts}
        assert len(ids) == 1  # All share same messageId

    def test_string_agent_result(self):
        with patch("factory.api.runtime.ag_ui_routes._call_tool",
                   side_effect=_mock_call_tool(agent_result="plain text")):
            client = _make_client()
            resp = client.post("/ag-ui/run", content=json.dumps({
                "messages": [{"role": "user", "content": "x"}],
            }))
        events = _parse_sse(resp.text)
        content = [e for e in events if e["type"] == "TEXT_MESSAGE_CONTENT"]
        assert content[0]["delta"] == "plain text"

