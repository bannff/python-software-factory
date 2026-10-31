"""Composed Workflow -> Agent native active-cancellation path."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from factory.agent.mcp.managed_graph_tool import register
from factory.agent.runtime.execution_manifest import (
    prepare_execution_manifest,
    store_manifest,
)
from factory.agent.runtime.graph_contracts import GraphConfig
from factory.mcp_utils.interface import (
    ExecutionBinding,
    acquire_service_entry,
    begin_service_invocation,
    end_service_invocation,
    mint_internal_invocation_claims,
    reset_internal_invocation_claims,
    set_internal_invocation_claims,
)
from factory.workflow.runtime.envelope import Envelope
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from .test_managed_graph import runtime


class Graph:
    def __init__(self, started: asyncio.Event, unwound: asyncio.Event) -> None:
        self.started, self.unwound, self.closed = started, unwound, False

    async def invoke_graph(self, request) -> None:
        del request
        self.started.set()
        try:
            await asyncio.Event().wait()
        finally:
            self.unwound.set()

    async def close(self) -> None:
        self.closed = True


class Capability:
    def __init__(self, **binding) -> None:
        self.binding = binding

    def dataset_port(self):
        return None

    async def persist(self, sequence, event, *, terminal) -> None:
        return None


class MCPInvoker:
    def __init__(self, mcp: ToolCatalog, loop: asyncio.AbstractEventLoop) -> None:
        self.mcp, self.loop = mcp, loop
        self.owner = None
        self.cancelled_error_seen = False
        self.calls: list[tuple] = []

    async def _call(self, target, arguments, attempt):
        tool = await self.mcp.get_tool(target.tool_name)
        binding = ExecutionBinding(**attempt)
        claims = mint_internal_invocation_claims(
            caller="workflow", audience="agent", target_tool=target.tool_name,
            binding=binding, target=tool,
        )
        token = set_internal_invocation_claims(claims)
        state = None
        try:
            state = begin_service_invocation(
                tool, audience="agent", target_tool=target.tool_name,
                arguments=arguments,
            )
            try:
                return await self.mcp.call_tool(target.tool_name, {
                    **arguments,
                    "_service_entry_authorization": acquire_service_entry(tool.fn),
                })
            except asyncio.CancelledError:
                self.cancelled_error_seen = True
                raise
        finally:
            end_service_invocation(state)
            reset_internal_invocation_claims(token)

    def invoke(
        self, *, target, arguments, idempotency_key, envelope, attempt=None,
    ):
        self.calls.append((target, arguments, idempotency_key, envelope, attempt))
        assert attempt == {
            key: arguments[key] for key in (
                "workflow_run_id", "attempt_id", "revision", "engine_id",
                "registration_digest", "request_digest", "provider_request_digest",
            )
        }
        if target.tool_name == "cancel_langgraph_attempt":
            run = self.owner.storage.get_run(run_id=arguments["workflow_run_id"])
            rows = self.owner.durable_storage.list_task_attempts(run_id=run.run_id)
            assert run.status == rows[-1]["status"] == "cancelled"
            assert rows[-1]["revision"] == arguments["revision"] + 1
        future = asyncio.run_coroutine_threadsafe(
            self._call(target, arguments, attempt), self.loop,
        )
        response = future.result(timeout=5)
        return {"ok": True, "result": {
            "kind": "tool", "content": [], "meta": {},
            "structured_content": response.structured_content,
        }}


def _manifest():
    config = GraphConfig.model_validate({
        "id": "graph", "name": "Graph", "nodes": [{
            "id": "worker", "type": "agent", "model": "model",
            "system_prompt": "work", "tools": [], "skills": [],
        }], "entry_point": "worker", "resumable": True,
    })
    return prepare_execution_manifest(config, "do work", {"domain": "planning"})


@pytest.mark.asyncio
async def test_real_native_stream_unwinds_only_after_durable_fence(
    tmp_path, monkeypatch,
) -> None:
    started, unwound = asyncio.Event(), asyncio.Event()
    graph = Graph(started, unwound)
    manifest = _manifest()
    descriptor = await store_manifest(manifest)
    monkeypatch.setattr(
        "factory.agent.runtime.adapters.create_runtime_pair",
        lambda *args, **kwargs: (
            SimpleNamespace(capability_scope_digest="a" * 64), graph,
        ),
    )
    monkeypatch.setattr(
        "factory.agent.mcp.managed_graph_tool.ManagedServiceCapability",
        Capability,
    )
    agent_mcp = ToolCatalog("agent-composed-cancellation")
    register(agent_mcp, SimpleNamespace())
    invoker = MCPInvoker(agent_mcp, asyncio.get_running_loop())
    owner = runtime(tmp_path, invoker, "langgraph")
    invoker.owner = owner
    running = asyncio.create_task(asyncio.to_thread(
        owner.enroll_execution,
        engine_id="langgraph", request=descriptor.model_dump(mode="json"),
        provider_request_digest=manifest.digest.value, run_key="key",
        envelope=Envelope(tenant_id="tenant", principal_id="owner"),
    ))
    started_wait = asyncio.create_task(started.wait())
    done, _ = await asyncio.wait(
        {running, started_wait}, timeout=5, return_when=asyncio.FIRST_COMPLETED,
    )
    assert done, "managed invocation did not start"
    early = running.result() if running in done else None
    assert started.is_set(), early
    record = owner.durable_storage.get_run_by_key(run_key="key")
    cancelled = await asyncio.to_thread(
        owner.cancel_run, run_id=record.run_id, reason="stop",
        envelope=Envelope(tenant_id="tenant", principal_id="owner"),
    )
    result = await asyncio.wait_for(running, timeout=5)
    assert cancelled["status"] == result["status"] == "cancelled"
    cancel_call = next(c for c in invoker.calls if c[0].tool_name == "cancel_langgraph_attempt")
    assert cancel_call[1] == cancel_call[4]
    assert cancel_call[1] == {
        "workflow_run_id": result["run_id"], "attempt_id": result["attempt_id"],
        "revision": 1, "engine_id": "langgraph",
        "registration_digest": result["registration_digest"],
        "request_digest": result["request_digest"],
        "provider_request_digest": manifest.digest.value,
    }
    assert unwound.is_set() and graph.closed
    assert invoker.cancelled_error_seen is True
    final = owner.storage.get_run(run_id=result["run_id"])
    attempt = owner.durable_storage.list_task_attempts(run_id=result["run_id"])[0]
    assert final.status == attempt["status"] == "cancelled"
    assert attempt["revision"] == 2
