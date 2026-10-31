"""Row 43 (Memory browser) single correction — ``memory_update`` MCP tool.

Covers the full round trip through the real tool catalog for both the
in-memory adapter (update supported) and a stub adapter with no ``update``
primitive at all, proving the runtime facade's honest "not supported on the
active backend" degradation (the graph adapter itself DOES support update —
see ``test_graph_store.py`` for its own adapter-level coverage).
"""
from __future__ import annotations

import asyncio

from factory.memory.runtime.adapters.memory import InMemoryStore
from factory.memory.runtime.runtime import MemoryRuntime
from factory.memory.server import create_mcp_server


def _tools(runtime: MemoryRuntime):
    catalog = create_mcp_server(runtime)
    return {tool.name: tool.fn for tool in asyncio.run(catalog.list_tools())}


def test_update_round_trips_through_the_real_tool_catalog() -> None:
    runtime = MemoryRuntime(InMemoryStore())
    tools = _tools(runtime)
    stored = tools["memory_store"](content="original", user_id="owner")
    memory_id = stored.data.memory.id

    result = tools["memory_update"](memory_id=memory_id, content="corrected")

    assert result.data.updated is True
    assert result.data.error is None
    assert result.data.memory.content == "corrected"
    refetched = tools["memory_get"](memory_id=memory_id)
    assert refetched.data.memory.content == "corrected"


def test_update_unknown_memory_reports_not_found() -> None:
    runtime = MemoryRuntime(InMemoryStore())
    tools = _tools(runtime)

    result = tools["memory_update"](memory_id="nonexistent-id", content="x")

    assert result.data.updated is False
    assert result.data.error == "memory not found"
    assert result.data.memory is None


class _NoUpdateStore(InMemoryStore):
    """A stub adapter that shadows ``update`` back to a non-callable so it
    is invisible to the runtime facade's ``getattr(..., "update", None)``
    duck-typing — proves the "not supported" reason is distinct from
    "not found" when the memory genuinely exists but the backend cannot
    mutate it."""

    update = None  # type: ignore[assignment]


def test_update_on_an_adapter_without_update_reports_not_supported() -> None:
    store = _NoUpdateStore()
    runtime = MemoryRuntime(store)
    tools = _tools(runtime)
    stored = tools["memory_store"](content="original", user_id="owner")
    memory_id = stored.data.memory.id

    result = tools["memory_update"](memory_id=memory_id, content="corrected")

    assert result.data.updated is False
    assert result.data.error == "memory update is not supported on the active backend"
    assert tools["memory_get"](memory_id=memory_id).data.memory.content == "original"


def test_update_preserves_the_same_protected_persistence_guard_as_store() -> None:
    """``memory_update`` calls the SAME ``validate_protected_persistence``
    guard ``memory_store`` already does, on the same shape — ``content`` is
    excluded from ``INLINE_SENSITIVE_FIELDS`` by design (defined in
    ``protected_fields.py``), so ordinary text content is never rejected
    by either tool. This proves the guard call is genuinely a no-op for
    normal content, not a silent behavior change from ``memory_store``."""
    runtime = MemoryRuntime(InMemoryStore())
    tools = _tools(runtime)
    stored = tools["memory_store"](content="AKIA1234567890ABCDEF", user_id="owner")
    assert stored.data.stored is True
    memory_id = stored.data.memory.id

    result = tools["memory_update"](memory_id=memory_id, content="still fine")

    assert result.data.updated is True
    assert result.data.memory.content == "still fine"
