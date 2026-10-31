"""Conformance tests for SDK-neutral Agent runtime contracts."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from factory.agent.runtime.runtime_contracts import (
    GraphEdge,
    GraphNode,
    GraphRequest,
    RuntimeAdapterDescriptor,
    RuntimeInvocation,
    RuntimeLifecycleEvent,
    RuntimeResult,
)
from factory.agent.runtime.runtime_ports import AgentRuntimePort, GraphRuntimePort


class _Runtime:
    descriptor = RuntimeAdapterDescriptor(
        adapter_id="langchain-langgraph",
        package_versions=(("langchain", "1.3.17"), ("langgraph", "1.2.11")),
        features=frozenset({"stream", "bounded_graph"}),
    )

    async def invoke(self, request: RuntimeInvocation) -> RuntimeResult:
        return RuntimeResult(request.invocation_id, request.prompt, "completed")

    async def stream(
        self, request: RuntimeInvocation,
    ) -> AsyncIterator[RuntimeLifecycleEvent]:
        yield RuntimeLifecycleEvent(request.invocation_id, 0, "started")
        yield RuntimeLifecycleEvent(request.invocation_id, 1, "completed")

    async def cancel(self, invocation_id: str) -> None:
        self.cancelled = invocation_id

    async def cancel_thread(self, thread_id: str) -> bool:
        self.cancelled_thread = thread_id
        return True

    async def close(self) -> None:
        self.closed = True

    async def invoke_graph(self, request: GraphRequest) -> RuntimeResult:
        return await self.invoke(request.invocation)

    async def stream_graph(
        self, request: GraphRequest,
    ) -> AsyncIterator[RuntimeLifecycleEvent]:
        async for event in self.stream(request.invocation):
            yield event


@pytest.mark.asyncio
async def test_runtime_ports_preserve_scope_and_normalized_events() -> None:
    runtime = _Runtime()
    request = RuntimeInvocation(
        invocation_id="attempt-1",
        agent_id="developer",
        prompt="inspect the capability",
        capability_scope_digest="scope-sha256",
        model_id="openai-compat/local",
        thread_id="thread-1",
        metadata={"correlation_id": "corr-1"},
    )

    assert isinstance(runtime, AgentRuntimePort)
    assert isinstance(runtime, GraphRuntimePort)
    assert runtime.descriptor.adapter_id == "langchain-langgraph"
    assert request.model_id == "openai-compat/local"
    assert runtime.descriptor.package_versions == (
        ("langchain", "1.3.17"), ("langgraph", "1.2.11"),
    )

    result = await runtime.invoke(request)
    assert result == RuntimeResult("attempt-1", "inspect the capability", "completed")
    assert [event.kind async for event in runtime.stream(request)] == [
        "started", "completed",
    ]

    graph = GraphRequest(
        invocation=request,
        nodes=(GraphNode("research", "researcher"), GraphNode("review", "reviewer")),
        edges=(GraphEdge("research", "review"),),
    )
    assert (await runtime.invoke_graph(graph)).invocation_id == request.invocation_id
    assert [event.sequence async for event in runtime.stream_graph(graph)] == [0, 1]

    await runtime.cancel(request.invocation_id)
    await runtime.close()
    assert runtime.cancelled == "attempt-1"
    assert runtime.closed is True


def test_contracts_are_available_from_the_public_agent_interface() -> None:
    from factory.agent.interface import AgentRuntimePort as PublicRuntimePort
    from factory.agent.interface import GraphRequest as PublicGraphRequest

    assert PublicRuntimePort is AgentRuntimePort
    assert PublicGraphRequest is GraphRequest


@pytest.mark.parametrize("tenant_id,owner_id", [
    ("tenant", None), (None, "owner"), ("", "owner"), ("tenant", " "),
])
def test_runtime_invocation_rejects_partial_or_blank_identity(
    tenant_id: str | None, owner_id: str | None,
) -> None:
    with pytest.raises(ValueError, match="tenant_id and owner_id"):
        RuntimeInvocation(
            invocation_id="attempt", agent_id="developer", prompt="x",
            capability_scope_digest="scope",
            tenant_id=tenant_id, owner_id=owner_id,
        )


def test_runtime_invocation_accepts_complete_or_absent_identity() -> None:
    base = dict(invocation_id="attempt", agent_id="developer", prompt="x",
                capability_scope_digest="scope")
    assert RuntimeInvocation(**base).tenant_id is None
    assert RuntimeInvocation(
        **base, tenant_id="tenant", owner_id="owner",
    ).owner_id == "owner"


def test_runtime_invocation_memory_mode_defaults_empty_and_validates() -> None:
    """Row 3 (feature-map): an unset mode means "no explicit choice was
    made" -- the session-binding seam resolves it, this contract just
    guards the value shape once one IS set."""
    base = dict(invocation_id="attempt", agent_id="developer", prompt="x",
                capability_scope_digest="scope")
    assert RuntimeInvocation(**base).memory_mode == ""
    assert RuntimeInvocation(**base, memory_mode="incognito").memory_mode == "incognito"
    with pytest.raises(ValueError, match="memory_mode"):
        RuntimeInvocation(**base, memory_mode="not-a-real-mode")
