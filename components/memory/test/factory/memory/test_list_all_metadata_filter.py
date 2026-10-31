"""Runtime-layer tests for ``MemoryRuntime.list_all(metadata=...)`` filter.

Owner ruling 2026-09-16 06:32 (rows 44/45 — Memory scope filter): the
Memory tab's default (no-query) browse view calls ``list_all``, not
``retrieve()`` — the metadata scope filter must work on both read paths or
the FE scope picker would silently do nothing until the user typed a
search term. Mirrors ``test_retrieve_metadata_filter.py``'s K1-K5 shape
for the read path that view actually uses.
"""
from __future__ import annotations

from factory.memory.runtime.adapters.memory import InMemoryStore
from factory.memory.runtime.runtime import MemoryRuntime


def _make_runtime() -> MemoryRuntime:
    return MemoryRuntime(store=InMemoryStore())


def test_list_all_metadata_none_and_empty_dict_both_mean_no_filter() -> None:
    rt = _make_runtime()
    rt.store(user_id="u1", content="a", metadata={"scope": "private"})
    rt.store(user_id="u1", content="b", metadata={"scope": "shared"})
    baseline = rt.list_all("u1")
    explicit_none = rt.list_all("u1", metadata=None)
    empty_dict = rt.list_all("u1", metadata={})
    assert {m.id for m in baseline} == {m.id for m in explicit_none} == {m.id for m in empty_dict}


def test_list_all_metadata_filters_to_matching_scope() -> None:
    rt = _make_runtime()
    private = rt.store(user_id="u1", content="private note", metadata={"scope": "private", "agent": "dev"})
    shared = rt.store(user_id="u1", content="shared note", metadata={"scope": "shared", "agent": "dev"})
    rt.store(user_id="u1", content="other agent", metadata={"scope": "shared", "agent": "ops"})
    filtered = rt.list_all("u1", metadata={"scope": "shared", "agent": "dev"})
    assert [m.id for m in filtered] == [shared.id]
    assert private.id not in {m.id for m in filtered}


def test_list_all_metadata_and_joins_multiple_keys() -> None:
    rt = _make_runtime()
    rt.store(user_id="u1", content="matches both", metadata={"agent": "dev", "scope": "shared"})
    rt.store(user_id="u1", content="wrong scope", metadata={"agent": "dev", "scope": "private"})
    filtered = rt.list_all("u1", metadata={"agent": "dev", "scope": "shared"})
    assert [m.content for m in filtered] == ["matches both"]


def test_list_all_memory_with_no_metadata_excluded_when_filter_set() -> None:
    rt = _make_runtime()
    rt.store(user_id="u1", content="no metadata at all")
    filtered = rt.list_all("u1", metadata={"scope": "shared"})
    assert filtered == []
