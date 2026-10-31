"""Hypothesis property tests for graph_sink — ToolInvocation materialisation.

Properties verified:
1. materialize never raises for any valid input combination
2. Anti-recursion guard skips graph_add*/graph_query* on brick="graph"
3. Env var gating: disabled sink never enqueues writes
4. Entity ID format: tool-inv-{12 hex chars}
5. Properties completeness: all required keys present in _call_graph call

graph_sink calls the graph brick DIRECTLY via _graph_runtime (a tool-name →
FunctionTool map) and enqueues writes to a background drain thread.  Tests
patch ``_call_graph`` to capture calls synchronously (avoiding drain-thread
timing issues).
"""
from __future__ import annotations

import asyncio
import os
import re
from unittest.mock import MagicMock, patch

from hypothesis import given, settings, strategies as st

from factory.graph.server import create_mcp_server
from factory.graph.runtime.runtime import GraphRuntime
from factory.graph.runtime.runtime import reset_runtime as reset_graph_runtime
from factory.mcp_server.runtime import graph_sink
from factory.mcp_utils.interface import push_envelope_updates, reset_envelope

# -- Strategies --
name_st = st.text(
    min_size=1, max_size=20,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)
latency_st = st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False)
error_st = st.one_of(st.none(), st.text(min_size=0, max_size=100))
recursive_tool_st = st.sampled_from([
    "graph_add_entity", "graph_add_relation", "graph_add_node",
    "graph_query_nodes", "graph_query_all",
])

ENTITY_RE = re.compile(r"^tool-inv-[0-9a-f]{12}$")
REQUIRED_KEYS = {"id", "brick_name", "tool_name", "success", "latency_ms", "error", "created_at"}


def _enable_env():
    return patch.dict(os.environ, {"TELEMETRY_GRAPH_SINK": "true"})


def _disable_env():
    return patch.dict(os.environ, {"TELEMETRY_GRAPH_SINK": "false"}, clear=False)


def _set_runtime_truthy():
    """Set _graph_runtime to a truthy sentinel so materialize passes the guard."""
    graph_sink._graph_runtime = {"sentinel": True}


def _clear_runtime():
    graph_sink._graph_runtime = None


def _clear_graph_sink_state() -> None:
    graph_sink._invocation_counter.clear()
    graph_sink._last_invocation_by_session.clear()
    graph_sink._run_invocation_counter.clear()
    graph_sink._last_invocation_by_run.clear()
    graph_sink._current_workflow_run_id = None


def _build_graph_tool_map() -> dict[str, object]:
    server = create_mcp_server(GraphRuntime(config={"default_backend": "networkx"}))
    tool_names = [
        "graph_add_entity",
        "graph_add_relationship",
        "graph_get_neighbors",
        "graph_list_recent_tool_invocations",
    ]
    return {
        name: asyncio.run(server.get_tool(name))
        for name in tool_names
    }


def _read_graph(tool_name: str, **kwargs):
    result = graph_sink._graph_runtime[tool_name].fn(**kwargs)
    assert result.ok and result.data is not None
    return result.data.model_dump()


def _run_queued_writes():
    """Drain the sink queue synchronously, mirroring the drain thread's error handling."""
    from queue import Empty
    while True:
        try:
            fn = graph_sink._SINK_QUEUE.get_nowait()
        except Empty:
            break
        if fn is not None:
            try:
                fn()
            except Exception:
                pass  # drain thread swallows errors too


# -- 1. materialize never raises --

@given(brick=name_st, tool=name_st, success=st.booleans(), lat=latency_st, err=error_st)
@settings(max_examples=50)
def test_materialize_never_raises(brick, tool, success, lat, err):
    """materialize swallows all errors — never raises regardless of inputs."""
    _set_runtime_truthy()
    try:
        with _enable_env(), \
             patch.object(graph_sink, "_call_graph", side_effect=RuntimeError("kaboom")), \
             patch.object(graph_sink, "_ensure_drain_thread"):
            graph_sink.materialize(brick, tool, success=success, latency_ms=lat, error=err)
            # Execute queued writes — they should swallow the error
            _run_queued_writes()
    finally:
        _clear_runtime()


@given(brick=name_st, tool=name_st, success=st.booleans(), lat=latency_st, err=error_st)
@settings(max_examples=50)
def test_materialize_never_raises_no_runtime(brick, tool, success, lat, err):
    """materialize is safe when _graph_runtime is None."""
    _clear_runtime()
    with _enable_env():
        graph_sink.materialize(brick, tool, success=success, latency_ms=lat, error=err)


# -- 2. Anti-recursion guard --

@given(tool=recursive_tool_st, success=st.booleans(), lat=latency_st, err=error_st)
@settings(max_examples=50)
def test_anti_recursion_skips_graph_calls(tool, success, lat, err):
    """When brick='graph' and tool starts with graph_add/graph_query, nothing is enqueued."""
    mock_call = MagicMock()
    _set_runtime_truthy()
    try:
        with _enable_env(), \
             patch.object(graph_sink, "_call_graph", mock_call), \
             patch.object(graph_sink, "_ensure_drain_thread"):
            graph_sink.materialize("graph", tool, success=success, latency_ms=lat, error=err)
            _run_queued_writes()
        mock_call.assert_not_called()
    finally:
        _clear_runtime()


@given(tool=name_st, success=st.booleans(), lat=latency_st)
@settings(max_examples=50)
def test_non_graph_brick_not_blocked(tool, success, lat):
    """Non-'graph' bricks are never blocked by the recursion guard."""
    mock_call = MagicMock(return_value=None)
    _set_runtime_truthy()
    try:
        with _enable_env(), \
             patch.object(graph_sink, "_call_graph", mock_call), \
             patch.object(graph_sink, "_ensure_drain_thread"):
            graph_sink.materialize("cache", tool, success=success, latency_ms=lat, error=None)
            _run_queued_writes()
        assert mock_call.call_count >= 1
    finally:
        _clear_runtime()


# -- 3. Env var gating --

@given(brick=name_st, tool=name_st, success=st.booleans(), lat=latency_st)
@settings(max_examples=50)
def test_disabled_env_skips_write(brick, tool, success, lat):
    """When TELEMETRY_GRAPH_SINK is 'false', _call_graph is never called."""
    mock_call = MagicMock()
    _set_runtime_truthy()
    try:
        with _disable_env(), \
             patch.object(graph_sink, "_call_graph", mock_call), \
             patch.object(graph_sink, "_ensure_drain_thread"):
            graph_sink.materialize(brick, tool, success=success, latency_ms=lat, error=None)
            _run_queued_writes()
        mock_call.assert_not_called()
    finally:
        _clear_runtime()


@given(brick=name_st, tool=name_st, success=st.booleans(), lat=latency_st)
@settings(max_examples=50)
def test_unset_env_skips_write(brick, tool, success, lat):
    """When TELEMETRY_GRAPH_SINK is absent, _call_graph is never called."""
    mock_call = MagicMock()
    _set_runtime_truthy()
    try:
        env = {k: v for k, v in os.environ.items() if k != "TELEMETRY_GRAPH_SINK"}
        with patch.dict(os.environ, env, clear=True), \
             patch.object(graph_sink, "_call_graph", mock_call), \
             patch.object(graph_sink, "_ensure_drain_thread"):
            graph_sink.materialize(brick, tool, success=success, latency_ms=lat, error=None)
            _run_queued_writes()
        mock_call.assert_not_called()
    finally:
        _clear_runtime()


# -- 4. Entity ID format --

@given(brick=name_st, tool=name_st, success=st.booleans(), lat=latency_st, err=error_st)
@settings(max_examples=50)
def test_entity_id_format(brick, tool, success, lat, err):
    """entity_id passed to _call_graph matches tool-inv-{12 hex chars}."""
    mock_call = MagicMock(return_value=None)
    _set_runtime_truthy()
    try:
        with _enable_env(), \
             patch.object(graph_sink, "_call_graph", mock_call), \
             patch.object(graph_sink, "_ensure_drain_thread"):
            graph_sink.materialize(brick, tool, success=success, latency_ms=lat, error=err)
            _run_queued_writes()
        # First call is graph_add_entity
        entity_id = mock_call.call_args_list[0].kwargs.get("entity_id")
        assert ENTITY_RE.match(entity_id), f"Bad entity_id: {entity_id}"
    finally:
        _clear_runtime()


# -- 5. Properties completeness --

@given(brick=name_st, tool=name_st, success=st.booleans(), lat=latency_st, err=error_st)
@settings(max_examples=50)
def test_properties_contain_all_required_keys(brick, tool, success, lat, err):
    """The properties dict passed to _call_graph has all required keys."""
    mock_call = MagicMock(return_value=None)
    _set_runtime_truthy()
    try:
        with _enable_env(), \
             patch.object(graph_sink, "_call_graph", mock_call), \
             patch.object(graph_sink, "_ensure_drain_thread"):
            graph_sink.materialize(brick, tool, success=success, latency_ms=lat, error=err)
            _run_queued_writes()
        # First call is graph_add_entity
        props = mock_call.call_args_list[0].kwargs.get("properties")
        assert REQUIRED_KEYS.issubset(props.keys()), f"Missing: {REQUIRED_KEYS - props.keys()}"
        assert props["brick_name"] == brick
        assert props["tool_name"] == tool
        assert props["success"] == success
        assert props["latency_ms"] == lat
        assert props["error"] == (err[:200] if err else None)
    finally:
        _clear_runtime()


def test_read_envelope_accepts_run_id_alias_for_workflow_run_id():
    with patch("factory.mcp_utils.interface.get_envelope", return_value={
        "session_id": "s1",
        "principal_id": "p1",
        "run_id": "run-42",
    }):
        session_id, principal_id, agent_id, workflow_run_id = graph_sink._read_envelope()

    assert session_id == "s1"
    assert principal_id == "p1"
    assert agent_id is None
    assert workflow_run_id == "run-42"


def test_materialize_persists_two_runs_into_queryable_timeline_history():
    queue_mock = MagicMock()
    queue_mock.put.side_effect = lambda fn: fn()

    reset_graph_runtime()
    _clear_graph_sink_state()
    prior_runtime = graph_sink._graph_runtime
    graph_sink._graph_runtime = _build_graph_tool_map()

    try:
        with _enable_env(), \
             patch.object(graph_sink, "_ensure_drain_thread"), \
             patch.object(graph_sink, "_SINK_QUEUE", queue_mock):
            token = push_envelope_updates(
                session_id="session-a",
                principal_id="principal-1",
                agent_id="agent-red",
                run_id="run-a",
            )
            try:
                graph_sink.materialize(
                    "agent",
                    "agent_reason",
                    success=True,
                    latency_ms=12.5,
                    caller="ag_ui",
                )
                graph_sink.materialize(
                    "cache",
                    "cache_get",
                    success=True,
                    latency_ms=3.0,
                    caller="ag_ui",
                )
            finally:
                reset_envelope(token)

            token = push_envelope_updates(
                session_id="session-b",
                principal_id="principal-1",
                agent_id="agent-blue",
                run_id="run-b",
            )
            try:
                graph_sink.materialize(
                    "agent",
                    "agent_reason",
                    success=False,
                    latency_ms=20.0,
                    error="boom",
                    caller="ag_ui",
                )
            finally:
                reset_envelope(token)

        timeline = _read_graph("graph_list_recent_tool_invocations", limit=100)
        session_a = _read_graph(
            "graph_get_neighbors",
            entity_id="session-session-a",
            relationship_type="CONTAINS_INVOCATION",
            direction="out",
        )
        session_b = _read_graph(
            "graph_get_neighbors",
            entity_id="session-session-b",
            relationship_type="CONTAINS_INVOCATION",
            direction="out",
        )
        run_a_sequence_counts = [
            _read_graph(
                "graph_get_neighbors",
                entity_id=neighbor["id"],
                relationship_type="FOLLOWED_BY",
                direction="out",
            )["count"]
            for neighbor in session_a["neighbors"]
        ]
        agent_a = _read_graph(
            "graph_get_neighbors",
            entity_id="session-session-a",
            relationship_type="EXECUTED_BY",
            direction="out",
        )
        initiator_a = _read_graph(
            "graph_get_neighbors",
            entity_id="session-session-a",
            relationship_type="INITIATED_BY",
            direction="out",
        )
        invoked_on = _read_graph(
            "graph_get_neighbors",
            entity_id=session_b["neighbors"][0]["id"],
            relationship_type="INVOKED_ON",
            direction="out",
        )

        assert [row["workflow_run_id"] for row in timeline["rows"]] == [
            "run-b",
            "run-a",
            "run-a",
        ]
        assert timeline["rows"][0]["success"] is False
        assert timeline["rows"][0]["error"] == "boom"
        assert all(row["caller"] == "ag_ui" for row in timeline["rows"])
        assert session_a["count"] == 2
        assert session_b["count"] == 1
        assert sorted(run_a_sequence_counts) == [0, 1]
        assert agent_a["count"] == 1
        assert agent_a["neighbors"][0]["id"] == "agent-agent-red"
        assert initiator_a["count"] == 1
        assert initiator_a["neighbors"][0]["id"] == "user-principal-1"
        assert invoked_on["count"] == 1
        assert invoked_on["neighbors"][0]["id"] == "brick-agent"
    finally:
        graph_sink._graph_runtime = prior_runtime
        _clear_graph_sink_state()
        reset_graph_runtime()


@given(
    session_id=st.one_of(st.none(), name_st),
    principal_id=st.one_of(st.none(), name_st),
    run_id=st.one_of(st.none(), name_st),
    workflow_run_id=st.one_of(st.none(), name_st),
)
@settings(max_examples=50)
def test_read_envelope_prefers_normalized_run_aliases(
    session_id, principal_id, run_id, workflow_run_id,
):
    expected = workflow_run_id or run_id
    with patch("factory.mcp_utils.interface.get_envelope", return_value={
        "session_id": session_id,
        "principal_id": principal_id,
        "agent_id": "agent-1",
        "run_id": run_id,
        "workflow_run_id": workflow_run_id,
    }):
        actual_session, actual_principal, actual_agent, actual_workflow = graph_sink._read_envelope()

    assert actual_session == session_id
    assert actual_principal == principal_id
    assert actual_agent == "agent-1"
    assert actual_workflow == expected
