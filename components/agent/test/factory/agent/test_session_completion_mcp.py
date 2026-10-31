from __future__ import annotations

from factory.agent.runtime.adapters.session_completions import SessionCompletionMCP
from factory.agent.runtime.runtime_contracts import RuntimeInvocation
from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.interface import ToolCatalog, get_service, set_service
from factory.session.runtime.adapters.completion_sql import SQLCompletionStore
from factory.session.runtime.adapters.sql import SQLSessionStore
from factory.session.runtime.completion import CompletionLifecycle
from factory.session.runtime.lifecycle import SessionLifecycle
from factory.session.runtime.runtime import SessionRuntime
from factory.session.server import create_tool_catalog
from factory.storage.interface import StorageRuntime


def test_agent_reads_and_acknowledges_origin_completion(tmp_path) -> None:
    sql = StorageRuntime().get_sql_store("sqlite", db_path=str(tmp_path / "db.sqlite"))
    store = SQLSessionStore(sql)
    sessions = SessionLifecycle(store)
    origin = sessions.create("tenant", "owner", "origin", "agent", "model")
    completions = CompletionLifecycle(SQLCompletionStore(sql), store)
    digest = completions.digest("ok", "finished")
    completions.record(
        "tenant", "owner", origin.session_id, "run:1",
        "ok", "finished", digest, 1,
    )
    child = create_tool_catalog(SessionRuntime(sessions, completions))
    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["session"])
    aggregator._lazy._cache["session"] = child
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", NativeEnvelopeInvoker(aggregator).for_caller)
    request = RuntimeInvocation(
        invocation_id="turn-1", agent_id="agent", prompt="continue",
        capability_scope_digest="scope", thread_id=origin.thread_id,
        tenant_id="tenant", owner_id="owner",
    )
    try:
        port = SessionCompletionMCP()
        pending = port.pending(request)
        assert len(pending) == 1 and pending[0].run_id == "run:1"
        assert port.acknowledge(pending[0]) is True
        assert port.pending(request) == ()
    finally:
        set_service("tool_invoker_for_caller", previous)
