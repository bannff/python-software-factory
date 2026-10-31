"""Stateful properties for the scoped capability test double."""

import asyncio

from hypothesis import given, settings, strategies as st

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


async def _handler(request: CapabilityInvocation) -> CapabilityResult:
    return CapabilityResult(content=({"json": request.arguments},))


@settings(max_examples=50)
@given(st.dictionaries(st.text(min_size=1, max_size=5), st.integers(), max_size=4))
def test_close_prevents_all_future_execution(arguments: dict[str, int]) -> None:
    async def scenario() -> None:
        scope = CapabilityScope.create("policy", {"allowed"})
        descriptor = CapabilityDescriptor("allowed", "test", {"type": "object"})
        client = InMemoryScopedCapabilityClient(scope, (descriptor,), {"allowed": _handler})
        request = CapabilityInvocation("allowed", arguments, "key", {"run": "one"})
        await client.invoke(request)
        await client.close()
        await client.close()
        try:
            await client.invoke(request)
        except CapabilityAccessError:
            pass
        else:  # pragma: no cover - property failure diagnostics
            raise AssertionError("closed client invoked a handler")
        assert client.calls == [request]

    asyncio.run(scenario())
