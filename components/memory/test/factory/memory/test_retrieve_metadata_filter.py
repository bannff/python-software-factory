"""Runtime-layer tests for ``MemoryRuntime.retrieve(metadata=...)`` filter.

bd:python-factory-b2d2o (epic python-factory-hadbi). Mirrors the lin6p
``tags`` test shape but pins the asymmetric default + AND semantics:

K1 ``metadata={}`` returns same set as ``metadata=None`` (no filter,
   asymmetric vs ``tags=[]``).
K2 ``metadata={"k": "v"}`` returns subset of ``metadata=None`` (monotonic).
K3 ``metadata={"k1": "v1", "k2": "v2"}`` AND-joins (all keys must match).
K4 Memory with no metadata is filtered OUT when filter is non-empty.
K5 Memory with partial match filtered OUT.
K6 Hypothesis: single-key filter ⊂ None (monotonic).
K7 Hypothesis: ``metadata={}`` ≡ ``metadata=None``.
K8 Cross-filter: ``tags + metadata`` is intersection of each filter alone.

K9 + K10 (Cypher-injection guard) live in ``test_metadata_safe_key.py``.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from hypothesis import given, settings, strategies as st

from factory.memory.runtime.adapters.memory import InMemoryStore
from factory.memory.runtime.runtime import MemoryRuntime


def _make_runtime() -> MemoryRuntime:
    return MemoryRuntime(store=InMemoryStore())


def _silent_invoker():
    return patch("factory.mcp_utils.registry._services", {"tool_invoker": MagicMock()})


# -- K1 — asymmetric default: None ≡ {} (NOT match-nothing) --


class TestMetadataNoneEqualsEmptyDict:
    def test_metadata_none_default_preserves_existing_behavior(self) -> None:
        rt = _make_runtime()
        rt.store(user_id="u1", content="alpha", metadata={"run_id": "r-1"})
        rt.store(user_id="u1", content="beta", metadata={"run_id": "r-2"})
        with _silent_invoker():
            baseline = rt.retrieve(user_id="u1", query="alpha", min_relevance=0.0)
            explicit_none = rt.retrieve(
                user_id="u1", query="alpha", min_relevance=0.0, metadata=None,
            )
        assert {m.id for m in baseline} == {m.id for m in explicit_none}

    def test_metadata_empty_dict_equals_none_no_filter(self) -> None:
        """K1: ``metadata={}`` is no-filter, NOT match-nothing."""
        rt = _make_runtime()
        rt.store(user_id="u1", content="alpha", metadata={"run_id": "r-1"})
        rt.store(user_id="u1", content="alpha-2", metadata={})
        rt.store(user_id="u1", content="alpha-3", metadata={"agent_id": "a-1"})
        with _silent_invoker():
            none_results = rt.retrieve(
                user_id="u1", query="alpha", min_relevance=0.0, metadata=None,
            )
            empty_results = rt.retrieve(
                user_id="u1", query="alpha", min_relevance=0.0, metadata={},
            )
        assert {m.id for m in none_results} == {m.id for m in empty_results}
        assert len(none_results) == 3


# -- K2..K5 — AND semantics across keys --


class TestMetadataAndSemantics:
    def test_single_key_returns_subset(self) -> None:
        rt = _make_runtime()
        wine = rt.store(user_id="u1", content="wine note",
                        metadata={"run_id": "r-1", "agent_id": "wine-1"})
        rt.store(user_id="u1", content="security note",
                 metadata={"run_id": "r-2", "agent_id": "sec-1"})
        with _silent_invoker():
            results = rt.retrieve(user_id="u1", query="note", min_relevance=0.0,
                                  metadata={"run_id": "r-1"})
        assert [m.id for m in results] == [wine.id]

    def test_two_keys_and_joined_both_must_match(self) -> None:
        rt = _make_runtime()
        match = rt.store(user_id="u1", content="x-y",
                         metadata={"run_id": "r-1", "target_app": "billing"})
        rt.store(user_id="u1", content="x-y-2",
                 metadata={"run_id": "r-1", "target_app": "auth"})
        rt.store(user_id="u1", content="x-y-3",
                 metadata={"run_id": "r-2", "target_app": "billing"})
        with _silent_invoker():
            results = rt.retrieve(
                user_id="u1", query="x-y", min_relevance=0.0,
                metadata={"run_id": "r-1", "target_app": "billing"},
            )
        assert [m.id for m in results] == [match.id]

    def test_memory_with_no_metadata_filtered_out_when_filter_set(self) -> None:
        rt = _make_runtime()
        rt.store(user_id="u1", content="bare", metadata={})
        rt.store(user_id="u1", content="bare-2", metadata={"run_id": "r-1"})
        with _silent_invoker():
            results = rt.retrieve(user_id="u1", query="bare", min_relevance=0.0,
                                  metadata={"run_id": "r-1"})
        assert all(m.metadata.get("run_id") == "r-1" for m in results)
        assert all(m.content != "bare" for m in results)

    def test_partial_match_filtered_out(self) -> None:
        """K5: only one of two required keys matches → filtered out."""
        rt = _make_runtime()
        rt.store(user_id="u1", content="probe", metadata={"run_id": "r-1"})
        with _silent_invoker():
            results = rt.retrieve(
                user_id="u1", query="probe", min_relevance=0.0,
                metadata={"run_id": "r-1", "target_app": "billing"},
            )
        assert results == []

    def test_value_mismatch_filtered_out(self) -> None:
        rt = _make_runtime()
        rt.store(user_id="u1", content="probe", metadata={"run_id": "r-1"})
        with _silent_invoker():
            results = rt.retrieve(user_id="u1", query="probe", min_relevance=0.0,
                                  metadata={"run_id": "r-2"})
        assert results == []


# -- K8 — cross-filter composition: tags ∧ metadata --


class TestTagsMetadataCompose:
    def test_intersection_when_both_filters_set(self) -> None:
        """K8: ``tags + metadata`` = intersection. Apply order: tags then
        metadata (verdict f279063c Q6)."""
        rt = _make_runtime()
        winner = rt.store(user_id="u1", content="m1",
                          metadata={"tags": ["x"], "run_id": "r-1"})
        rt.store(user_id="u1", content="m2",
                 metadata={"tags": ["x"], "run_id": "r-2"})
        rt.store(user_id="u1", content="m3",
                 metadata={"tags": ["y"], "run_id": "r-1"})
        with _silent_invoker():
            results = rt.retrieve(user_id="u1", query="m", min_relevance=0.0,
                                  tags=["x"], metadata={"run_id": "r-1"})
        assert [m.id for m in results] == [winner.id]

    def test_tags_empty_short_circuits_even_with_metadata_set(self) -> None:
        """``tags=[]`` matches nothing; metadata cannot rescue it."""
        rt = _make_runtime()
        rt.store(user_id="u1", content="m1",
                 metadata={"tags": ["x"], "run_id": "r-1"})
        with _silent_invoker():
            results = rt.retrieve(user_id="u1", query="m", min_relevance=0.0,
                                  tags=[], metadata={"run_id": "r-1"})
        assert results == []


# -- K6 + K7 — Hypothesis property tests --


_VALUE_ALPHABET = st.text(
    alphabet=st.sampled_from(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-",
    ),
    min_size=1, max_size=8,
)
_SAFE_KEYS = st.sampled_from(["run_id", "agent_id", "target_app", "trace_id"])
_PROPERTY_SETTINGS = settings(max_examples=30, deadline=None)


@_PROPERTY_SETTINGS
@given(stored=st.dictionaries(_SAFE_KEYS, _VALUE_ALPHABET, min_size=0, max_size=3),
       filter_key=_SAFE_KEYS, filter_value=_VALUE_ALPHABET)
def test_metadata_single_filter_is_subset_of_none(
    stored: dict[str, str], filter_key: str, filter_value: str,
) -> None:
    """K6: single-key filter ⊂ None."""
    rt = _make_runtime()
    rt.store(user_id="u1", content="probe content", metadata=stored)
    with _silent_invoker():
        unfiltered = rt.retrieve(user_id="u1", query="probe content",
                                 min_relevance=0.0, metadata=None)
        filtered = rt.retrieve(user_id="u1", query="probe content",
                               min_relevance=0.0,
                               metadata={filter_key: filter_value})
    assert {m.id for m in filtered}.issubset({m.id for m in unfiltered})


@_PROPERTY_SETTINGS
@given(stored=st.dictionaries(_SAFE_KEYS, _VALUE_ALPHABET, min_size=0, max_size=3))
def test_metadata_empty_dict_equivalent_to_none(stored: dict[str, str]) -> None:
    """K7: ``metadata={}`` and ``metadata=None`` return identical sets."""
    rt = _make_runtime()
    rt.store(user_id="u1", content="probe content", metadata=stored)
    with _silent_invoker():
        none_results = rt.retrieve(user_id="u1", query="probe content",
                                   min_relevance=0.0, metadata=None)
        empty_results = rt.retrieve(user_id="u1", query="probe content",
                                    min_relevance=0.0, metadata={})
    assert {m.id for m in none_results} == {m.id for m in empty_results}
