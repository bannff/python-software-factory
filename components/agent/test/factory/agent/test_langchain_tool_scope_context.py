"""LangChain capability calls bind and reset their exact effective scope."""
from __future__ import annotations

import pytest
pytest.importorskip("langchain")
pytest.importorskip("langgraph")
pytest.importorskip("langchain_community")

from factory.agent.runtime.adapters.langchain_tools import (
    bind_invocation, build_langchain_tools, reset_invocation,
)
from factory.agent.runtime.runtime_contracts import RuntimeInvocation
from factory.mcp_utils.interface import (
    CapabilityDescriptor, CapabilityResult, CapabilityScope,
    get_capability_scope,
)
from factory.mcp_utils.runtime.scoped_capability_client import (
    InMemoryScopedCapabilityClient,
)


def _request(scope: CapabilityScope) -> RuntimeInvocation:
    return RuntimeInvocation("run", "agent", "task", scope.digest)


@pytest.mark.asyncio
@pytest.mark.parametrize("raises", [False, True])
async def test_exact_scope_resets_after_client_success_or_exception(raises: bool) -> None:
    base = CapabilityScope.create("p", {"allowed", "hidden"})
    effective = CapabilityScope.create("p", {"allowed"})

    async def handler(_request):
        assert get_capability_scope() == effective
        if raises:
            raise RuntimeError("expected")
        return CapabilityResult(())

    client = InMemoryScopedCapabilityClient(
        base,
        (
            CapabilityDescriptor("allowed", "", {"type": "object", "properties": {}}),
            CapabilityDescriptor("hidden", "", {"type": "object", "properties": {}}),
        ),
        {"allowed": handler},
    )
    tools = await build_langchain_tools(client, effective)
    assert [tool.name for tool in tools] == ["allowed"]
    invocation_token = bind_invocation(_request(base))
    try:
        if raises:
            with pytest.raises(RuntimeError, match="expected"):
                await tools[0].ainvoke({})
        else:
            await tools[0].ainvoke({})
        assert get_capability_scope() is None
    finally:
        reset_invocation(invocation_token)
