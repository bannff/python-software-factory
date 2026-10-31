from __future__ import annotations

import pytest

from factory.agent.runtime.managed_steering import ManagedSteeringRegistry


@pytest.mark.asyncio
async def test_registry_offers_only_to_active_managed_runtime() -> None:
    registry = ManagedSteeringRegistry()
    request = object()

    class Runtime:
        calls = []

        async def offer_steer(self, supplied, send_id, content):
            self.calls.append((supplied, send_id, content))
            return "accepted"

    runtime = Runtime()
    assert await registry.offer("run-1", "send-0", "early") is None
    registry.register("run-1", runtime, request)
    assert await registry.offer("run-1", "send-1", "redirect") == "accepted"
    assert runtime.calls == [(request, "send-1", "redirect")]
    registry.unregister("run-1", runtime)
    assert await registry.offer("run-1", "send-2", "late") is None


def test_registry_rejects_duplicate_live_owner() -> None:
    registry = ManagedSteeringRegistry()
    runtime = object()

    async def register() -> None:
        registry.register("run-1", runtime, object())
        with pytest.raises(RuntimeError, match="already active"):
            registry.register("run-1", object(), object())

    import asyncio
    asyncio.run(register())
