"""Agent steering uses Session only through the native MCP service seam."""
from __future__ import annotations

from factory.agent.runtime.adapters.session_steering import SessionSteeringMCP
from factory.agent.runtime.runtime_contracts import RuntimeInvocation
from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.interface import ToolCatalog, get_service, set_service
from factory.session.runtime.adapters.sql import SQLSessionStore
from factory.session.runtime.lifecycle import SessionLifecycle
from factory.session.runtime.models import SteerState
from factory.session.runtime.runtime import SessionRuntime
from factory.session.server import create_tool_catalog
from factory.storage.interface import StorageRuntime


def test_agent_registers_reads_and_settles_through_session_mcp(
    tmp_path, monkeypatch,
) -> None:
    from factory.mcp_utils.interface import (
        event_bus, push_envelope_updates, reset_envelope,
    )
    events: list[dict] = []
    monkeypatch.setattr(event_bus, "publish", events.append)
    envelope_token = push_envelope_updates(
        session_id="thread-1", correlation_id="chat-run-1",
    )
    sql = StorageRuntime().get_sql_store(
        "sqlite", db_path=str(tmp_path / "sessions.db"),
    )
    lifecycle = SessionLifecycle(SQLSessionStore(sql))
    child = create_tool_catalog(SessionRuntime(lifecycle))
    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["session"])
    aggregator._lazy._cache["session"] = child
    native = NativeEnvelopeInvoker(aggregator)
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", native.for_caller)
    try:
        port = SessionSteeringMCP()
        request = RuntimeInvocation(
            invocation_id="run-1", agent_id="companion-x-default", prompt="start",
            capability_scope_digest="scope", model_id="openrouter/deepseek/test",
            thread_id="thread-1", tenant_id="tenant-1", owner_id="owner-1",
        )
        session_id = port.ensure(request)
        assert session_id and port.ensure(request) == session_id
        session = lifecycle.resolve_thread("tenant-1", "owner-1", "thread-1")
        assert session.session_id == session_id
        assert session.title == "start"
        assert session.model == "openrouter/deepseek/test"

        first = port.write(request, "send-1", "change direction")
        deliveries = port.written(request)
        assert [item.delivery_id for item in deliveries] == [first.delivery_id]
        assert port.consume(deliveries[0]) is True
        assert lifecycle.get_steer(
            "tenant-1", "owner-1", session_id, first.delivery_id,
        ).state is SteerState.CONSUMED

        second = port.write(request, "send-2", "too late")
        assert port.requeue_written(request) == (second.delivery_id,)

        delivery_events = [
            event for event in events if event.get("event_type") == "session.steer"
        ]
        assert [event["payload"]["state"] for event in delivery_events] == [
            "written", "consumed", "written", "requeued",
        ]
        assert all("content" not in event["payload"] for event in delivery_events)
        assert all(
            event["payload"]["correlation_id"] == "chat-run-1"
            for event in delivery_events
        )
        assert lifecycle.get_steer(
            "tenant-1", "owner-1", session_id, second.delivery_id,
        ).state is SteerState.REQUEUED
    finally:
        set_service("tool_invoker_for_caller", previous)
        reset_envelope(envelope_token)


def test_bind_materializes_the_session_memory_mode(tmp_path, monkeypatch) -> None:
    """Row 3 (feature-map): an explicit per-chat mode on the FIRST request
    for a thread lands on the durable session, and every subsequent bind()
    for that same thread reflects the session's real materialized mode --
    never silently reverting to the caller's original (possibly stale or
    absent) value."""
    from factory.mcp_utils.interface import push_envelope_updates, reset_envelope

    envelope_token = push_envelope_updates(session_id="thread-mode", correlation_id="run-1")
    sql = StorageRuntime().get_sql_store("sqlite", db_path=str(tmp_path / "sessions.db"))
    lifecycle = SessionLifecycle(SQLSessionStore(sql))
    child = create_tool_catalog(SessionRuntime(lifecycle))
    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["session"])
    aggregator._lazy._cache["session"] = child
    native = NativeEnvelopeInvoker(aggregator)
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", native.for_caller)
    try:
        port = SessionSteeringMCP()
        first_request = RuntimeInvocation(
            invocation_id="run-1", agent_id="companion-x-default", prompt="a sensitive question",
            capability_scope_digest="scope", model_id="openrouter/deepseek/test",
            thread_id="thread-mode", tenant_id="tenant-1", owner_id="owner-1",
            memory_mode="incognito",
        )
        bound = port.bind(first_request)
        assert bound.memory_mode == "incognito"

        # A later turn on the SAME thread carries no explicit choice -- the
        # already-materialized session mode must still win, not "persistent".
        later_request = RuntimeInvocation(
            invocation_id="run-2", agent_id="companion-x-default", prompt="follow-up",
            capability_scope_digest="scope", model_id="openrouter/deepseek/test",
            thread_id="thread-mode", tenant_id="tenant-1", owner_id="owner-1",
        )
        later_bound = port.bind(later_request)
        assert later_bound.memory_mode == "incognito"
    finally:
        set_service("tool_invoker_for_caller", previous)
        reset_envelope(envelope_token)


def test_bind_defaults_to_persistent_when_no_explicit_mode_was_ever_chosen(
    tmp_path, monkeypatch,
) -> None:
    from factory.mcp_utils.interface import push_envelope_updates, reset_envelope

    envelope_token = push_envelope_updates(session_id="thread-default", correlation_id="run-1")
    sql = StorageRuntime().get_sql_store("sqlite", db_path=str(tmp_path / "sessions.db"))
    lifecycle = SessionLifecycle(SQLSessionStore(sql))
    child = create_tool_catalog(SessionRuntime(lifecycle))
    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["session"])
    aggregator._lazy._cache["session"] = child
    native = NativeEnvelopeInvoker(aggregator)
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", native.for_caller)
    try:
        port = SessionSteeringMCP()
        request = RuntimeInvocation(
            invocation_id="run-1", agent_id="companion-x-default", prompt="hi",
            capability_scope_digest="scope", model_id="openrouter/deepseek/test",
            thread_id="thread-default", tenant_id="tenant-1", owner_id="owner-1",
        )
        assert port.bind(request).memory_mode == "persistent"
    finally:
        set_service("tool_invoker_for_caller", previous)
        reset_envelope(envelope_token)
