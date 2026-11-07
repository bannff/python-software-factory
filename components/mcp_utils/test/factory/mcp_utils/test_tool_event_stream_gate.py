"""The tool poller must only query the graph when the sink writes that data.

With ``TELEMETRY_GRAPH_SINK`` off, ``graph_sink.materialize`` returns early, so
no ``ToolInvocation`` entities exist; polling then costs one empty graph query
per second per connected client. The poll reads the flag per iteration, so a
flip at runtime takes effect without reconnecting.
"""
from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from factory.mcp_utils import tool_event_stream
from factory.mcp_utils.graph_sink_gate import GRAPH_SINK_ENV


class _Result:
    class _Data:
        entities: list[Any] = []

    data = _Data()


class _RecordingInvoker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, tool: str, **kwargs: Any) -> _Result:
        self.calls.append((tool, kwargs))
        return _Result()


def _start_consumer() -> asyncio.Task:
    async def _drain() -> None:
        async for _ in tool_event_stream.tool_invocation_stream(last_seen=0):
            pass

    return asyncio.create_task(_drain())


async def _stop(task: asyncio.Task) -> None:
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await task


async def _consume(seconds: float) -> None:
    task = _start_consumer()
    await asyncio.sleep(seconds)
    await _stop(task)


async def test_stream_does_not_poll_when_sink_is_disabled(monkeypatch) -> None:
    monkeypatch.setenv(GRAPH_SINK_ENV, "0")
    invoker = _RecordingInvoker()
    monkeypatch.setattr(tool_event_stream, "_get_invoker", lambda: invoker)

    await _consume(seconds=0.5)

    assert invoker.calls == []


async def test_stream_polls_when_sink_is_enabled(monkeypatch) -> None:
    monkeypatch.setenv(GRAPH_SINK_ENV, "1")
    invoker = _RecordingInvoker()
    monkeypatch.setattr(tool_event_stream, "_get_invoker", lambda: invoker)

    await _consume(seconds=0.4)

    assert invoker.calls, "expected at least one graph poll"
    tool, kwargs = invoker.calls[0]
    assert tool == "graph_find_entities"
    assert kwargs["entity_type"] == "ToolInvocation"


async def test_enabling_the_sink_mid_stream_starts_polling(monkeypatch) -> None:
    monkeypatch.setenv(GRAPH_SINK_ENV, "0")
    invoker = _RecordingInvoker()
    monkeypatch.setattr(tool_event_stream, "_get_invoker", lambda: invoker)

    task = _start_consumer()
    await asyncio.sleep(0.3)
    assert invoker.calls == [], "disabled sink must not poll"

    monkeypatch.setenv(GRAPH_SINK_ENV, "1")
    await asyncio.sleep(1.4)

    await _stop(task)

    assert invoker.calls, "enabling the sink must start polling on the live stream"


async def test_stream_does_not_poll_without_a_tool_invoker(monkeypatch) -> None:
    monkeypatch.setenv(GRAPH_SINK_ENV, "1")
    monkeypatch.setattr(tool_event_stream, "_get_invoker", lambda: None)

    await _consume(seconds=0.3)  # must not raise; nothing to poll with
