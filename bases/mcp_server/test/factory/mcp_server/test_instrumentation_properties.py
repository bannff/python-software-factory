"""Hypothesis property tests for OTel tool call instrumentation.

Properties verified:
1. Passthrough: traced wrappers return exactly what fn returns
2. Exception passthrough: wrappers re-raise the same exception
3. Async passthrough: traced_tool_call matches sync and async fn results
4. Span attributes: OTel spans get correct brick.name and tool.name
5. Error recording: exceptions trigger span.record_exception + ERROR status
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, strategies as st

from factory.mcp_utils.interface import push_envelope_updates, reset_envelope
from factory.mcp_server.runtime.instrumentation import (
    traced_tool_call,
    traced_tool_call_sync,
)

# -- Strategies --
name_st = st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N")))
kwargs_st = st.dictionaries(
    st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L",))),
    st.integers(),
    max_size=5,
)
return_st = st.one_of(st.integers(), st.text(max_size=30), st.none())


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is None:
        return asyncio.run(coro)
    return loop.run_until_complete(coro)


# -- 1. Passthrough property (sync) --

@given(brick=name_st, tool=name_st, kw=kwargs_st, ret=return_st)
@settings(max_examples=50)
def test_sync_passthrough(brick, tool, kw, ret):
    """traced_tool_call_sync returns exactly what fn(**kwargs) returns."""
    fn = MagicMock(return_value=ret)
    result = traced_tool_call_sync(brick, tool, fn, kw)
    assert result == ret
    fn.assert_called_once_with(**kw)


# -- 2. Exception passthrough (sync) --

@given(brick=name_st, tool=name_st, kw=kwargs_st)
@settings(max_examples=50)
def test_sync_exception_passthrough(brick, tool, kw):
    """traced_tool_call_sync re-raises the same exception from fn."""
    exc = ValueError("boom")
    fn = MagicMock(side_effect=exc)
    try:
        traced_tool_call_sync(brick, tool, fn, kw)
        assert False, "Should have raised"
    except ValueError as caught:
        assert caught is exc


# -- 3. Async passthrough (sync fn through async wrapper) --

@given(brick=name_st, tool=name_st, kw=kwargs_st, ret=return_st)
@settings(max_examples=50)
def test_async_passthrough_sync_fn(brick, tool, kw, ret):
    """traced_tool_call returns same result as fn for a sync callable."""
    fn = MagicMock(return_value=ret)
    result = _run_async(traced_tool_call(brick, tool, fn, kw))
    assert result == ret


# -- 3b. Async passthrough (async fn through async wrapper) --

@given(brick=name_st, tool=name_st, kw=kwargs_st, ret=return_st)
@settings(max_examples=50)
def test_async_passthrough_async_fn(brick, tool, kw, ret):
    """traced_tool_call awaits and returns same result for an async callable."""
    async def async_fn(**_kw):
        return ret

    result = _run_async(traced_tool_call(brick, tool, async_fn, kw))
    assert result == ret


# -- 3c. Async exception passthrough --

@given(brick=name_st, tool=name_st, kw=kwargs_st)
@settings(max_examples=50)
def test_async_exception_passthrough(brick, tool, kw):
    """traced_tool_call re-raises exceptions from async fn."""
    exc = RuntimeError("async boom")

    async def bad_fn(**_kw):
        raise exc

    try:
        _run_async(traced_tool_call(brick, tool, bad_fn, kw))
        assert False, "Should have raised"
    except RuntimeError as caught:
        assert caught is exc


# -- 4. Span attributes (mock tracer) --

@given(brick=name_st, tool=name_st, kw=kwargs_st, ret=return_st)
@settings(max_examples=50)
def test_span_attributes(brick, tool, kw, ret):
    """When OTel is available, span gets brick.name and tool.name attributes."""
    mock_span = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_span)
    mock_cm.__exit__ = MagicMock(return_value=False)
    mock_tracer = MagicMock()
    mock_tracer.start_as_current_span.return_value = mock_cm

    fn = MagicMock(return_value=ret)
    with patch("factory.mcp_server.runtime.instrumentation._HAS_OTEL", True), \
         patch("factory.mcp_server.runtime.instrumentation._tracer", mock_tracer):
        result = traced_tool_call_sync(brick, tool, fn, kw)

    assert result == ret
    mock_tracer.start_as_current_span.assert_called_once()
    call_kwargs = mock_tracer.start_as_current_span.call_args
    assert call_kwargs[1]["attributes"]["brick.name"] == brick
    assert call_kwargs[1]["attributes"]["tool.name"] == tool


# -- 5. Error recording --

@given(brick=name_st, tool=name_st, kw=kwargs_st)
@settings(max_examples=50)
def test_error_recording(brick, tool, kw):
    """When fn raises and OTel is available, span records exception and ERROR status."""
    mock_span = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_span)
    mock_cm.__exit__ = MagicMock(return_value=False)
    mock_tracer = MagicMock()
    mock_tracer.start_as_current_span.return_value = mock_cm

    exc = TypeError("test error")
    fn = MagicMock(side_effect=exc)
    with patch("factory.mcp_server.runtime.instrumentation._HAS_OTEL", True), \
         patch("factory.mcp_server.runtime.instrumentation._tracer", mock_tracer):
        try:
            traced_tool_call_sync(brick, tool, fn, kw)
            assert False, "Should have raised"
        except TypeError:
            pass

    mock_span.record_exception.assert_called_once()
    recorded = mock_span.record_exception.call_args.args[0]
    assert type(recorded) is RuntimeError
    assert "test error" not in str(recorded)
    mock_span.set_status.assert_called_once()
    status_args = mock_span.set_status.call_args[0]
    # StatusCode.ERROR == 2 in the OTel enum
    assert status_args[0].value == 2


def test_sync_publish_includes_live_run_and_session_context():
    """Live event payload includes workflow and session identity from envelope context."""
    fn = MagicMock(return_value={"ok": True})
    token = push_envelope_updates(
        session_id="session-42",
        principal_id="principal-7",
        run_id="run-42",
    )
    try:
        with patch("factory.mcp_server.runtime.instrumentation.graph_sink.materialize") as mock_materialize, \
             patch("factory.mcp_server.runtime.instrumentation.event_bus.publish") as mock_publish:
            result = traced_tool_call_sync("agent", "agent_reason", fn, {"task": "scan"})

        assert result == {"ok": True}
        mock_materialize.assert_called_once()
        published = mock_publish.call_args.args[0]
        assert published["caller"] == "principal-7"
        assert published["session_id"] == "session-42"
        assert published["workflow_run_id"] == "run-42"
    finally:
        reset_envelope(token)


def test_live_context_falls_back_to_graph_sink_run_id_when_envelope_empty():
    """When envelope contextvar is empty, _read_live_context falls back to
    factory.mcp_server.interface.get_workflow_run_id() — the cross-thread
    safety net for tool calls dispatched via _AGENT_POOL where contextvar
    propagation has historically been brittle (python-factory-zlqx)."""
    from factory.mcp_server.runtime.instrumentation import _read_live_context

    # Empty envelope, but graph_sink global is set (mirrors the worker-pool
    # case where contextvars don't survive the asyncio.run boundary).
    with patch("factory.mcp_utils.interface.get_envelope", return_value={}), \
         patch(
            "factory.mcp_server.interface.get_workflow_run_id",
            return_value="run-fallback-42",
         ):
        caller, session_id, workflow_run_id = _read_live_context()

    assert caller == "unknown"
    assert session_id is None
    assert workflow_run_id == "run-fallback-42"


def test_live_context_envelope_takes_precedence_over_fallback():
    """Envelope is the primary source — fallback only fires when envelope is empty."""
    from factory.mcp_server.runtime.instrumentation import _read_live_context

    # Envelope has run_id; the fallback should NOT be consulted.
    with patch(
        "factory.mcp_utils.interface.get_envelope",
        return_value={
            "session_id": "s-primary", "principal_id": "p-primary",
            "run_id": "run-from-envelope",
        },
    ), patch(
        "factory.mcp_server.interface.get_workflow_run_id",
        return_value="run-from-fallback-WRONG",
    ) as mock_fallback:
        caller, session_id, workflow_run_id = _read_live_context()

    assert caller == "p-primary"
    assert session_id == "s-primary"
    assert workflow_run_id == "run-from-envelope"
    # The fallback must not have been called when envelope already has a run_id.
    mock_fallback.assert_not_called()


def test_sync_publish_uses_graph_sink_fallback_when_envelope_empty():
    """End-to-end: a tool call with an empty envelope still publishes a live
    event with the right workflow_run_id from the graph_sink fallback."""
    fn = MagicMock(return_value={"ok": True})
    # No envelope push — simulating the worker-pool case where the
    # contextvar is missing inside the fresh asyncio.run loop.
    with patch(
        "factory.mcp_server.interface.get_workflow_run_id",
        return_value="run-pool-99",
    ), patch(
        "factory.mcp_server.runtime.instrumentation.graph_sink.materialize",
    ), patch(
        "factory.mcp_server.runtime.instrumentation.event_bus.publish",
    ) as mock_publish:
        result = traced_tool_call_sync(
            "security", "security.recon", fn, {"target": "vampi"},
        )

    assert result == {"ok": True}
    published = mock_publish.call_args.args[0]
    # Caller defaults to 'unknown' (no envelope, no caller_hint)
    assert published.get("caller") in (None, "unknown")
    # workflow_run_id MUST come from the fallback
    assert published["workflow_run_id"] == "run-pool-99"


def _contains(value, needle: str) -> bool:
    if isinstance(value, dict):
        return any(_contains(key, needle) or _contains(item, needle) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains(item, needle) for item in value)
    return needle in str(value)


def test_protected_call_never_copies_business_canary_to_graph_events_or_otel():
    """Direct traced call proves every observability rail gets a safe projection."""
    canary = "business-canary@example.test / secret-subject / body"
    graph, events = MagicMock(), MagicMock()
    span, cm, tracer = MagicMock(), MagicMock(), MagicMock()
    cm.__enter__.return_value, cm.__exit__.return_value = span, False
    tracer.start_as_current_span.return_value = cm
    protected = {"artifact_ref": "pc_v1_abcdefghijklmnopqrstuv", "fingerprint": "a" * 64,
                 "body": canary, "subject": canary, "recipients": [canary],
                 "nested": {"query": canary}}
    with patch("factory.mcp_server.runtime.instrumentation._HAS_OTEL", True), \
         patch("factory.mcp_server.runtime.instrumentation._tracer", tracer), \
         patch("factory.mcp_server.runtime.instrumentation.graph_sink.materialize", graph), \
         patch("factory.mcp_server.runtime.instrumentation.event_bus.publish", events):
        assert traced_tool_call_sync("integrations", "send_email", lambda **_: {"provider_response": canary, "count": 1}, protected)["count"] == 1
        with pytest.raises(ValueError):
            traced_tool_call_sync("integrations", "send_email", lambda **_: (_ for _ in ()).throw(ValueError(canary)), protected)
    captured = [graph.call_args_list, events.call_args_list, span.record_exception.call_args_list,
                span.set_status.call_args_list, tracer.start_as_current_span.call_args_list]
    assert not _contains(captured, canary)
