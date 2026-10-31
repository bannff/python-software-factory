"""Row 3 (feature-map) — owner ruling 2026-09-16 21:20: "Incognito: read
memory, write nothing; Temporary: read nothing, write nothing." Real,
tool-dispatch-boundary proof that the memory_mode gate actually blocks
(or allows) the exact tool calls the ruling names.
"""
from __future__ import annotations

import pytest

pytest.importorskip("langchain")

from factory.agent.runtime.adapters.langchain_tools import (
    bind_invocation, build_langchain_tools, reset_invocation,
)
from factory.agent.runtime.runtime_contracts import RuntimeInvocation
from factory.mcp_utils.interface import CapabilityDescriptor, CapabilityResult, CapabilityScope
from factory.mcp_utils.runtime.scoped_capability_client import InMemoryScopedCapabilityClient


def _scope_and_client(tool_name: str):
    calls: list[int] = []
    scope = CapabilityScope.create("memory-mode-test", {tool_name})

    async def handler(_request):
        calls.append(1)
        return CapabilityResult(())

    client = InMemoryScopedCapabilityClient(
        scope,
        (CapabilityDescriptor(tool_name, "demo", {"type": "object", "properties": {}}),),
        {tool_name: handler},
    )
    return scope, client, calls


async def _invoke_named_tool(tool_name: str, memory_mode: str) -> tuple[dict, list[int]]:
    scope, client, calls = _scope_and_client(tool_name)
    tools = await build_langchain_tools(client, scope)
    token = bind_invocation(RuntimeInvocation(
        "run", "agent", "task", scope.digest,
        tenant_id="tenant", owner_id="owner", memory_mode=memory_mode,
    ))
    try:
        result = await tools[0].ainvoke({})
    finally:
        reset_invocation(token)
    return result, calls


@pytest.mark.asyncio
async def test_incognito_blocks_memory_store_but_allows_memory_retrieve() -> None:
    write_result, write_calls = await _invoke_named_tool("memory_store", "incognito")
    assert write_result["is_error"] is True
    assert write_result["structured_content"]["error"] == "memory_mode_incognito_blocks_memory_write"
    assert write_calls == []

    read_result, read_calls = await _invoke_named_tool("memory_retrieve", "incognito")
    assert read_result["is_error"] is False
    assert read_calls == [1]


@pytest.mark.asyncio
async def test_temporary_blocks_both_memory_write_and_read() -> None:
    write_result, write_calls = await _invoke_named_tool("memory_store", "temporary")
    assert write_result["is_error"] is True
    assert write_result["structured_content"]["error"] == "memory_mode_temporary_blocks_memory"
    assert write_calls == []

    read_result, read_calls = await _invoke_named_tool("memory_retrieve", "temporary")
    assert read_result["is_error"] is True
    assert read_result["structured_content"]["error"] == "memory_mode_temporary_blocks_memory"
    assert read_calls == []


@pytest.mark.asyncio
async def test_persistent_and_unset_mode_never_restrict_memory() -> None:
    for mode in ("persistent", ""):
        write_result, write_calls = await _invoke_named_tool("memory_store", mode)
        assert write_result["is_error"] is False
        assert write_calls == [1]


@pytest.mark.asyncio
async def test_memory_mode_gate_never_affects_non_memory_tools() -> None:
    """The gate is scoped strictly to the memory brick's own tools (owner
    ruling wording: "memory" specifically) — an unrelated tool name must
    never be caught by the same-shaped ``memory_`` prefix or any other
    accidental overlap."""
    result, calls = await _invoke_named_tool("devtools_read_file", "temporary")
    assert result["is_error"] is False
    assert calls == [1]
