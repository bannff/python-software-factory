from __future__ import annotations

import pytest
pytest.importorskip("langchain")
pytest.importorskip("langgraph")
pytest.importorskip("langchain_community")

from factory.agent.runtime.adapters.langgraph_runtime import LangGraphRuntime
from factory.agent.runtime.runtime_contracts import (
    GraphNode, GraphRequest, RuntimeInvocation, RuntimeResult,
)


@pytest.mark.asyncio
async def test_background_node_preserves_child_session_identity() -> None:
    class Agents:
        seen = []

        async def invoke(self, request):
            self.seen.append(request)
            return RuntimeResult(request.invocation_id, "done", "completed")

        async def close(self):
            return None

    agents = Agents()
    graph = LangGraphRuntime(agents)
    request = GraphRequest(
        invocation=RuntimeInvocation(
            invocation_id="run-1", agent_id="background-graph", prompt="work",
            capability_scope_digest="scope", thread_id="bg_thread",
            tenant_id="tenant", owner_id="owner",
            metadata={"background_subagent": "true"},
        ),
        nodes=(GraphNode("worker", "worker"),), edges=(),
    )
    result = await graph.invoke_graph(request)
    assert result.status == "completed"
    child = agents.seen[0]
    assert child.thread_id == "bg_thread"
    assert (child.tenant_id, child.owner_id, child.agent_id) == (
        "tenant", "owner", "worker",
    )
    await graph.close()
