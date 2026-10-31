"""Tests for the per-run SSE stream endpoint — GET /api/stream/run/{run_id}.

bd:python-factory-tko13
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch, MagicMock


def _make_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from starlette.middleware.cors import CORSMiddleware
    from factory.mcp_utils.interface import cors_options
    from factory.api.runtime.run_stream_routes import register_run_stream_routes

    app = FastAPI()
    app.add_middleware(CORSMiddleware, **cors_options())
    register_run_stream_routes(app)
    return TestClient(app)


def _parse_sse(raw: str) -> list[dict]:
    """Parse SSE text into list of event dicts."""
    events = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def _make_event_bus(events: list[dict], stall: bool = False):
    """Return a mock event_bus whose subscribe() yields the given events.

    If ``stall=True``, the generator sleeps after the events so the
    caller can simulate a live connection that hasn't disconnected yet.
    """

    async def _subscribe():
        for evt in events:
            yield evt
        if stall:
            await asyncio.sleep(60)

    bus = MagicMock()
    bus.subscribe = _subscribe
    return bus


class TestRunStreamEndpoint:
    """GET /api/stream/run/{run_id} — SSE route."""

    def test_matching_event_appears_in_stream(self):
        """An event tagged with the requested run_id is emitted as SSE."""
        matching = {"run_id": "test-run-123", "type": "node_start", "data": "x"}
        bus = _make_event_bus([matching])

        with patch("factory.mcp_utils.interface.event_bus", bus):
            client = _make_client()
            resp = client.get("/api/stream/run/test-run-123")

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        events = _parse_sse(resp.text)
        assert len(events) == 1
        assert events[0]["run_id"] == "test-run-123"
        assert events[0]["type"] == "node_start"

    def test_non_matching_run_id_filtered_out(self):
        """Events tagged with a different run_id are silently dropped."""
        other = {"run_id": "other-run-999", "type": "node_start"}
        matching = {"run_id": "test-run-123", "type": "done"}
        bus = _make_event_bus([other, matching])

        with patch("factory.mcp_utils.interface.event_bus", bus):
            client = _make_client()
            resp = client.get("/api/stream/run/test-run-123")

        events = _parse_sse(resp.text)
        assert len(events) == 1
        assert events[0]["type"] == "done"

    def test_workflow_run_id_field_also_matches(self):
        """Events using workflow_run_id (instead of run_id) are also matched."""
        evt = {"workflow_run_id": "test-run-123", "type": "swarm_handoff"}
        bus = _make_event_bus([evt])

        with patch("factory.mcp_utils.interface.event_bus", bus):
            client = _make_client()
            resp = client.get("/api/stream/run/test-run-123")

        events = _parse_sse(resp.text)
        assert len(events) == 1
        assert events[0]["type"] == "swarm_handoff"

    def test_nested_payload_run_id_matches(self):
        """Events with run_id inside a 'payload' sub-dict are also matched."""
        evt = {"type": "graph.node_start", "payload": {"run_id": "test-run-123"}}
        bus = _make_event_bus([evt])

        with patch("factory.mcp_utils.interface.event_bus", bus):
            client = _make_client()
            resp = client.get("/api/stream/run/test-run-123")

        events = _parse_sse(resp.text)
        assert len(events) == 1

    def test_non_dict_events_ignored(self):
        """Non-dict events (e.g. bare strings) are silently skipped."""

        async def _subscribe():
            yield "not-a-dict"
            yield {"run_id": "test-run-123", "type": "real_event"}

        bus = MagicMock()
        bus.subscribe = _subscribe

        with patch("factory.mcp_utils.interface.event_bus", bus):
            client = _make_client()
            resp = client.get("/api/stream/run/test-run-123")

        events = _parse_sse(resp.text)
        assert len(events) == 1
        assert events[0]["type"] == "real_event"

    def test_cors_headers_present(self):
        """CORSMiddleware echoes an allowed origin on the SSE response."""
        bus = _make_event_bus([])

        with patch("factory.mcp_utils.interface.event_bus", bus):
            client = _make_client()
            resp = client.get("/api/stream/run/test-run-123",
                              headers={"Origin": "http://localhost:3000"})

        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_options_preflight(self):
        """CORSMiddleware answers the preflight for an allowed origin."""
        client = _make_client()
        resp = client.options("/api/stream/run/test-run-123", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        })
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert "GET" in resp.headers.get("access-control-allow-methods", "")

    def test_empty_bus_returns_empty_stream(self):
        """When no events are emitted the response body is empty but valid."""
        bus = _make_event_bus([])

        with patch("factory.mcp_utils.interface.event_bus", bus):
            client = _make_client()
            resp = client.get("/api/stream/run/test-run-123")

        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        assert events == []

    def test_multiple_matching_events_all_emitted(self):
        """All matching events for a run_id appear in order."""
        evts = [
            {"run_id": "run-abc", "type": "start", "seq": 1},
            {"run_id": "run-abc", "type": "mid", "seq": 2},
            {"run_id": "run-abc", "type": "end", "seq": 3},
        ]
        bus = _make_event_bus(evts)

        with patch("factory.mcp_utils.interface.event_bus", bus):
            client = _make_client()
            resp = client.get("/api/stream/run/run-abc")

        events = _parse_sse(resp.text)
        assert len(events) == 3
        assert [e["seq"] for e in events] == [1, 2, 3]
