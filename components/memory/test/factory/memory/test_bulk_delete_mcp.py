"""Row 43 bulk correction — owner ruling: bulk delete of matched memories
only, no bulk content edit. ``memory_bulk_preview``/``memory_bulk_delete``
share the exact same filter logic (via ``MemoryRuntime.bulk_delete`` and
its duplicated match code in the preview tool) so a shown count can never
disagree with what a real delete removes.
"""
from __future__ import annotations

import asyncio

from factory.memory.interface import create_server
from factory.memory.runtime.adapters.memory import InMemoryStore
from factory.memory.runtime.runtime import MemoryRuntime


def _call_tool(server, tool_name: str, **kwargs):
    tool = asyncio.run(server.get_tool(tool_name))
    if tool is None:
        raise ValueError(f"Tool '{tool_name}' not found.")
    return tool.fn(**kwargs)


def test_bulk_delete_removes_only_memories_matching_the_type_filter() -> None:
    runtime = MemoryRuntime(store=InMemoryStore())
    runtime.store(user_id="u1", content="a short fact", memory_type="short_term")
    runtime.store(user_id="u1", content="another short fact", memory_type="short_term")
    kept = runtime.store(user_id="u1", content="a long fact", memory_type="long_term")
    server = create_server(runtime)

    preview = _call_tool(server, "memory_bulk_preview", user_id="u1", memory_type="short_term")
    assert preview.data.matched_count == 2

    result = _call_tool(server, "memory_bulk_delete", user_id="u1", memory_type="short_term")

    assert result.data.deleted_count == 2
    remaining = runtime.list_all("u1", 100)
    assert [m.id for m in remaining] == [kept.id]


def test_bulk_delete_with_a_query_matches_the_same_set_the_preview_showed() -> None:
    runtime = MemoryRuntime(store=InMemoryStore())
    target = runtime.store(user_id="u1", content="the quick brown fox jumps")
    other = runtime.store(user_id="u1", content="zzz")
    server = create_server(runtime)

    preview = _call_tool(server, "memory_bulk_preview", user_id="u1", query="the quick brown fox jumps")
    assert preview.data.matched_count == 1
    assert preview.data.sample[0].id == target.id

    result = _call_tool(server, "memory_bulk_delete", user_id="u1", query="the quick brown fox jumps")

    assert result.data.deleted_count == 1
    assert result.data.deleted_ids == [target.id]
    remaining = runtime.list_all("u1", 100)
    assert [m.id for m in remaining] == [other.id]


def test_bulk_delete_with_no_filter_deletes_every_memory_for_the_user_only() -> None:
    runtime = MemoryRuntime(store=InMemoryStore())
    runtime.store(user_id="u1", content="a")
    runtime.store(user_id="u1", content="b")
    other_user = runtime.store(user_id="u2", content="c")
    server = create_server(runtime)

    result = _call_tool(server, "memory_bulk_delete", user_id="u1")

    assert result.data.deleted_count == 2
    assert runtime.list_all("u1", 100) == []
    assert [m.id for m in runtime.list_all("u2", 100)] == [other_user.id]


def test_bulk_preview_and_delete_fail_closed_with_no_ambient_identity() -> None:
    runtime = MemoryRuntime(store=InMemoryStore())
    server = create_server(runtime)

    preview = _call_tool(server, "memory_bulk_preview")
    delete = _call_tool(server, "memory_bulk_delete")

    assert preview.data.matched_count == 0
    assert preview.data.error is not None
    assert delete.data.deleted_count == 0
    assert delete.data.error is not None
