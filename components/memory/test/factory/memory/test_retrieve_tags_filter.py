"""Runtime-layer tests for ``MemoryRuntime.retrieve(tags=...)`` filter.

bd:python-factory-lin6p (epic python-factory-hadbi). Pins:

* ``tags=None`` (default) preserves today's behaviour (back-compat).
* ``tags=[]`` matches NOTHING (distinct from ``None``).
* Non-empty list = ANY-match: a memory with any matching ``metadata.tags``
  entry is returned, others are filtered out.
* Memory whose metadata has no ``tags`` key is filtered out when the
  caller supplies a non-None filter — back-compat path is the
  ``tags=None`` default.
* Hypothesis fuzz pins monotonicity: ``tags=[X]`` results are a subset
  of ``tags=None`` results, and ``tags=[]`` is always empty.

Post-filter lives in ``MemoryRuntime.retrieve`` (not in any adapter), so
the in-memory adapter exercises the same code path as future tier 2/3
adapters.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from hypothesis import given, settings, strategies as st

from factory.memory.runtime.adapters.memory import InMemoryStore
from factory.memory.runtime.runtime import MemoryRuntime


def _make_runtime() -> MemoryRuntime:
    return MemoryRuntime(store=InMemoryStore())


def _silent_invoker():
    """Patch the events publish bridge to keep tests focused on filter logic."""
    return patch("factory.mcp_utils.registry._services", {"tool_invoker": MagicMock()})


class TestTagsNoneBackCompat:
    def test_tags_none_default_preserves_existing_behavior(self) -> None:
        rt = _make_runtime()
        rt.store(user_id="u1", content="alpha", metadata={"tags": ["x"]})
        rt.store(user_id="u1", content="beta", metadata={"tags": ["y"]})
        with _silent_invoker():
            baseline = rt.retrieve(user_id="u1", query="alpha", min_relevance=0.0)
            explicit_none = rt.retrieve(
                user_id="u1", query="alpha", min_relevance=0.0, tags=None,
            )
        assert {m.id for m in baseline} == {m.id for m in explicit_none}

    def test_memory_with_no_tags_included_when_filter_none(self) -> None:
        rt = _make_runtime()
        rt.store(user_id="u1", content="hello world", metadata={})
        with _silent_invoker():
            results = rt.retrieve(
                user_id="u1", query="hello world", min_relevance=0.0, tags=None,
            )
        assert len(results) == 1


class TestTagsEmptyMatchesNothing:
    def test_tags_empty_list_matches_nothing(self) -> None:
        rt = _make_runtime()
        rt.store(user_id="u1", content="alpha", metadata={"tags": ["x"]})
        rt.store(user_id="u1", content="beta", metadata={"tags": ["y"]})
        with _silent_invoker():
            results = rt.retrieve(
                user_id="u1", query="alpha", min_relevance=0.0, tags=[],
            )
        assert results == []


class TestTagsAnyMatch:
    def test_single_filter_returns_subset(self) -> None:
        rt = _make_runtime()
        wine = rt.store(
            user_id="u1", content="wine pairing tip",
            metadata={"tags": ["wine-pairing-learnings", "run-1"]},
        )
        rt.store(
            user_id="u1", content="security note",
            metadata={"tags": ["security-learnings", "run-1"]},
        )
        with _silent_invoker():
            results = rt.retrieve(
                user_id="u1", query="wine", min_relevance=0.0,
                tags=["wine-pairing-learnings"],
            )
        assert [m.id for m in results] == [wine.id]

    def test_no_match_returns_empty(self) -> None:
        rt = _make_runtime()
        rt.store(
            user_id="u1", content="security note",
            metadata={"tags": ["security-learnings"]},
        )
        with _silent_invoker():
            results = rt.retrieve(
                user_id="u1", query="security", min_relevance=0.0,
                tags=["wine-pairing-learnings"],
            )
        assert results == []

    def test_or_semantics_returns_both_matches(self) -> None:
        rt = _make_runtime()
        a = rt.store(user_id="u1", content="a-note", metadata={"tags": ["x"]})
        b = rt.store(user_id="u1", content="b-note", metadata={"tags": ["y"]})
        rt.store(user_id="u1", content="c-note", metadata={"tags": ["z"]})
        with _silent_invoker():
            results = rt.retrieve(
                user_id="u1", query="note", min_relevance=0.0, tags=["x", "y"],
            )
        ids = {m.id for m in results}
        assert ids == {a.id, b.id}

    def test_memory_with_no_tags_filtered_out_when_filter_set(self) -> None:
        rt = _make_runtime()
        rt.store(user_id="u1", content="bare", metadata={})
        rt.store(user_id="u1", content="other", metadata={"tags": ["x"]})
        with _silent_invoker():
            results = rt.retrieve(
                user_id="u1", query="bare", min_relevance=0.0, tags=["x"],
            )
        # Only the memory with metadata.tags=["x"] survives the filter.
        assert all("x" in m.metadata.get("tags", []) for m in results)
        assert all(m.content != "bare" for m in results)

    def test_filter_matches_set_or_tuple_metadata_tags(self) -> None:
        """metadata.tags stored as tuple/set still ANY-matches."""
        rt = _make_runtime()
        rt.store(user_id="u1", content="tuple-tags", metadata={"tags": ("x", "y")})
        with _silent_invoker():
            results = rt.retrieve(
                user_id="u1", query="tuple-tags", min_relevance=0.0, tags=["y"],
            )
        assert len(results) == 1

    def test_memory_with_empty_tags_list_filtered_out(self) -> None:
        """metadata.tags=[] is False under any non-None filter (J6)."""
        rt = _make_runtime()
        rt.store(user_id="u1", content="empty-tags", metadata={"tags": []})
        with _silent_invoker():
            results = rt.retrieve(
                user_id="u1", query="empty-tags", min_relevance=0.0, tags=["x"],
            )
        assert results == []


_TAG_ALPHABET = st.text(
    alphabet=st.sampled_from(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
    ),
    min_size=1, max_size=12,
)


_PROPERTY_SETTINGS = settings(max_examples=30, deadline=None)


@_PROPERTY_SETTINGS
@given(stored_tags=st.lists(_TAG_ALPHABET, min_size=0, max_size=4))
def test_tags_empty_always_empty(stored_tags: list[str]) -> None:
    """``tags=[]`` returns ``[]`` regardless of stored memories."""
    rt = _make_runtime()
    rt.store(
        user_id="u1", content="probe content",
        metadata={"tags": list(stored_tags)},
    )
    with _silent_invoker():
        results = rt.retrieve(
            user_id="u1", query="probe content", min_relevance=0.0, tags=[],
        )
    assert results == []


@_PROPERTY_SETTINGS
@given(
    stored_tags=st.lists(_TAG_ALPHABET, min_size=0, max_size=4),
    filter_tag=_TAG_ALPHABET,
)
def test_tags_none_is_superset_of_single_filter(
    stored_tags: list[str], filter_tag: str,
) -> None:
    """Filter is monotonic — ``tags=[X]`` is a subset of ``tags=None``."""
    rt = _make_runtime()
    rt.store(
        user_id="u1", content="probe content",
        metadata={"tags": list(stored_tags)},
    )
    with _silent_invoker():
        unfiltered = rt.retrieve(
            user_id="u1", query="probe content",
            min_relevance=0.0, tags=None,
        )
        filtered = rt.retrieve(
            user_id="u1", query="probe content",
            min_relevance=0.0, tags=[filter_tag],
        )
    assert {m.id for m in filtered}.issubset({m.id for m in unfiltered})
