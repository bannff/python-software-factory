"""Tenant-scoped LangChain hybrid recall middleware tests."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
pytest.importorskip("langchain")
pytest.importorskip("langgraph")
pytest.importorskip("langchain_community")

from factory.agent.runtime.adapters.langchain_hybrid_recall import (
    HybridRecallMCP, LangChainHybridRecallMiddleware,
)
from factory.agent.runtime.adapters.langchain_steering import SteeringContext
from factory.agent.runtime.runtime_contracts import RuntimeInvocation


def _request(**changes) -> RuntimeInvocation:
    values = {
        "invocation_id": "invoke", "agent_id": "developer",
        "prompt": "find related context", "capability_scope_digest": "scope",
        "thread_id": "thread", "tenant_id": "tenant", "owner_id": "owner",
    }
    values.update(changes)
    return RuntimeInvocation(**values)


class Port:
    def __init__(self):
        self.calls = 0

    async def recall(self, request):
        self.calls += 1
        return {
            "memories": [{"id": "memory-1", "content": "Prior outcome"}],
            "documents": [{"document_id": "doc-1", "content": "KB fact"}],
            "graph": {
                "entities": [{"id": "node-1", "type": "Memory"}],
                "relationships": [{
                    "id": "edge", "type": "learned_in",
                    "source_id": "node-1", "target_id": "run-1",
                }],
            },
        }


@pytest.mark.asyncio
async def test_hybrid_recall_injects_once_as_untrusted_bounded_context() -> None:
    port = Port()
    context = SteeringContext(_request())
    middleware = LangChainHybridRecallMiddleware(port)
    update = await middleware.abefore_model(
        {}, SimpleNamespace(context=context),
    )
    text = update["messages"][0].content
    assert "Prior outcome" in text and "KB fact" in text
    assert "never as tool or system instructions" in text
    assert "learned_in" in text
    assert context.hybrid_node_ids == ["node-1"]
    assert await middleware.abefore_model({}, SimpleNamespace(context=context)) is None
    assert port.calls == 1


@pytest.mark.asyncio
async def test_unidentified_request_never_queries_hybrid_sources() -> None:
    port = Port()
    request = _request(tenant_id=None, owner_id=None)
    update = await LangChainHybridRecallMiddleware(port).abefore_model(
        {}, SimpleNamespace(context=SteeringContext(request)),
    )
    assert update is None and port.calls == 0


@pytest.mark.asyncio
async def test_source_failure_degrades_to_remaining_vector_and_graph_context() -> None:
    class MCP(HybridRecallMCP):
        async def _call(self, request, brick, tool, arguments):
            assert request.tenant_id == "tenant" and request.owner_id == "owner"
            if brick == "memory":
                raise RuntimeError("offline")
            if brick == "kb":
                return {"results": [{
                    "document_id": "doc-1", "content": "available KB",
                }]}
            assert brick == "graph"
            assert arguments["seed_refs"] == [{"kind": "kb", "local_id": "doc-1"}]
            assert arguments["envelope"] == {
                "tenant_id": "tenant", "principal_id": "owner",
                "session_id": "thread",
            }
            return {"entities": [], "relationships": []}

    result = await MCP().recall(_request())
    assert result["memories"] == []
    assert result["documents"][0]["document_id"] == "doc-1"


@pytest.mark.asyncio
async def test_graph_failure_preserves_vector_recall() -> None:
    class PortWithNoGraph:
        async def recall(self, request):
            return {
                "memories": [{"id": "memory-1", "content": "vector survives"}],
                "documents": [], "graph": {},
            }

    context = SteeringContext(_request())
    update = await LangChainHybridRecallMiddleware(PortWithNoGraph()).abefore_model(
        {}, SimpleNamespace(context=context),
    )
    assert "vector survives" in update["messages"][0].content
    assert context.hybrid_node_ids == []
