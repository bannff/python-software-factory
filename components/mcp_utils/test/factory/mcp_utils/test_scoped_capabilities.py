"""Conformance tests for the dependency-free scoped capability client."""

import pytest

from factory.mcp_utils.interface import (
    CapabilityDescriptor,
    CapabilityInvocation,
    CapabilityResult,
    CapabilityScope,
)
from factory.mcp_utils.runtime.scoped_capability_client import (
    CapabilityAccessError,
    InMemoryScopedCapabilityClient,
)


async def _result(request: CapabilityInvocation) -> CapabilityResult:
    return CapabilityResult(content=({"text": request.arguments["value"]},))


def _client() -> InMemoryScopedCapabilityClient:
    scope = CapabilityScope.create("policy", {"allowed"})
    descriptor = CapabilityDescriptor("allowed", "test", {"type": "object"})
    return InMemoryScopedCapabilityClient(scope, (descriptor,), {"allowed": _result})


@pytest.mark.asyncio
async def test_scope_preserves_raw_request_and_hides_other_descriptors() -> None:
    client = _client()
    request = CapabilityInvocation("allowed", {"value": {"nested": []}}, "key", {"run": "one"})
    result = await client.invoke(request)
    assert [item.name for item in await client.list_capabilities()] == ["allowed"]
    assert result.content == ({"text": {"nested": []}},)
    assert client.calls == [request]


@pytest.mark.asyncio
async def test_scope_denial_never_calls_a_handler() -> None:
    client = _client()
    with pytest.raises(CapabilityAccessError, match="outside scope"):
        await client.invoke(CapabilityInvocation("blocked", {}, "key"))
    assert client.calls == []


@pytest.mark.asyncio
async def test_close_is_idempotent_and_blocks_every_operation() -> None:
    client = _client()
    await client.close()
    await client.close()
    with pytest.raises(CapabilityAccessError, match="closed"):
        await client.list_capabilities()
    with pytest.raises(CapabilityAccessError, match="closed"):
        await client.invoke(CapabilityInvocation("allowed", {}, "key"))
