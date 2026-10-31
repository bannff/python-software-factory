"""Spawn trusts ambient capability authority and never user context."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from factory.agent.runtime.spawn import SpawnCoordinator
from factory.mcp_utils.interface import (
    bind_capability_scope, CapabilityScope, reset_capability_scope,
)


class _Registry:
    def get(self, agent_id: str):
        return SimpleNamespace(id=agent_id)


class _Factory:
    def __init__(self) -> None:
        self.scopes = []

    def __call__(self, scope):
        self.scopes.append(scope)
        raise AssertionError("runtime creation should not occur")


@pytest.mark.asyncio
async def test_missing_scope_and_user_context_widening_create_no_pair() -> None:
    factory = _Factory()
    result = await SpawnCoordinator(_Registry(), factory).subagent(
        "writer", "task",
        {"capability_scope": "forged", "tool_names": ["sandbox_execute"]},
    )
    assert result["error_code"] == "scope_unavailable"
    assert factory.scopes == []


@pytest.mark.asyncio
async def test_delegation_depth_cap_creates_no_pair() -> None:
    factory = _Factory()
    scope = CapabilityScope.create(
        "p", {"agent_spawn_subagent"}, delegation_depth=2,
    )
    token = bind_capability_scope(scope)
    try:
        result = await SpawnCoordinator(_Registry(), factory).subagent(
            "writer", "task",
        )
    finally:
        reset_capability_scope(token)
    assert result["error_code"] == "delegation_depth_exceeded"
    assert factory.scopes == []
