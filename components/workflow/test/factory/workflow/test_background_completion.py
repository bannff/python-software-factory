from __future__ import annotations

from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.interface import ToolCatalog, get_service, set_service
from factory.session.runtime.adapters.completion_sql import SQLCompletionStore
from factory.session.runtime.adapters.sql import SQLSessionStore
from factory.session.runtime.completion import CompletionLifecycle
from factory.session.runtime.lifecycle import SessionLifecycle
from factory.session.runtime.runtime import SessionRuntime
from factory.session.server import create_tool_catalog
from factory.workflow.runtime.envelope import Envelope

from .test_managed_graph import DIGEST, GraphInvoker, descriptor, runtime


def _session_surface(tmp_path):
    from factory.storage.interface import StorageRuntime
    sql = StorageRuntime().get_sql_store("sqlite", db_path=str(tmp_path / "sessions.db"))
    store = SQLSessionStore(sql)
    lifecycle = SessionLifecycle(store)
    origin = lifecycle.create("tenant", "owner", "origin", "agent", "model")
    completion = CompletionLifecycle(SQLCompletionStore(sql), store)
    child = create_tool_catalog(SessionRuntime(lifecycle, completion))
    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["session"])
    aggregator._lazy._cache["session"] = child
    return origin, completion, NativeEnvelopeInvoker(aggregator)


def test_terminal_background_run_records_origin_completion_once(tmp_path) -> None:
    origin, completion, native = _session_surface(tmp_path)
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", native.for_caller)
    try:
        owner = runtime(tmp_path, GraphInvoker())
        authority = Envelope(
            tenant_id="tenant", principal_id="owner", session_id=origin.thread_id,
        )
        admitted = owner.enroll_execution(
            engine_id="strands_graph", request=descriptor(),
            provider_request_digest=DIGEST, run_key="complete-key",
            envelope=authority, execute=False, launch_metadata={
                "kind": "background_subagent", "origin_session_id": origin.session_id,
            },
        )
        owner.resume_run(run_id=admitted["run_id"], envelope=authority)
        owner.resume_run(run_id=admitted["run_id"], envelope=authority)
    finally:
        set_service("tool_invoker_for_caller", previous)
    pending = completion.pending("tenant", "owner", origin.session_id)
    assert len(pending) == 1
    assert pending[0].run_id == admitted["run_id"]
    assert pending[0].outcome.value == "ok"
    events = owner.storage.get_events_since(run_id=admitted["run_id"], after_event_id=0)
    assert [event.event_type for event in events].count(
        "system.background_completion_recorded",
    ) == 1


def test_cancelled_background_run_records_stopped_completion(tmp_path) -> None:
    origin, completion, native = _session_surface(tmp_path)
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", native.for_caller)
    try:
        owner = runtime(tmp_path, GraphInvoker())
        authority = Envelope(tenant_id="tenant", principal_id="owner")
        admitted = owner.enroll_execution(
            engine_id="strands_graph", request=descriptor(),
            provider_request_digest=DIGEST, run_key="cancel-key",
            envelope=authority,
            execute=False, launch_metadata={
                "kind": "background_subagent", "origin_session_id": origin.session_id,
            },
        )
        owner.cancel_run(
            run_id=admitted["run_id"], reason="user stopped",
            envelope=authority,
        )
    finally:
        set_service("tool_invoker_for_caller", previous)
    pending = completion.pending("tenant", "owner", origin.session_id)
    assert len(pending) == 1 and pending[0].outcome.value == "stopped"
