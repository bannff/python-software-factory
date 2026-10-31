"""Tests for rapidfuzz-backed similarity in InMemoryStore.

Verifies that the rapidfuzz library is wired into the memory adapter
and produces correct fuzzy matching behavior.
"""

from __future__ import annotations

import pytest

from factory.memory.runtime.adapters.memory import InMemoryStore
from factory.memory.runtime.models import MemoryQuery


class TestRapidFuzzSimilarity:
    """Tests for rapidfuzz integration in InMemoryStore."""

    def test_import(self) -> None:
        """rapidfuzz is importable."""
        from rapidfuzz import fuzz
        assert fuzz.ratio is not None

    def test_exact_match_high_relevance(self) -> None:
        """Exact string match should score high."""
        store = InMemoryStore()
        store.store("u1", "dark mode preference")
        results = store.retrieve(MemoryQuery(
            user_id="u1", query="dark mode preference", limit=5,
        ))
        assert len(results) > 0
        assert results[0].relevance_score > 0.8

    def test_similar_strings_score_higher(self) -> None:
        """Similar content ranks above dissimilar content."""
        store = InMemoryStore()
        store.store("u1", "The user prefers dark mode for the UI")
        store.store("u1", "The user enjoys hiking on weekends")
        results = store.retrieve(MemoryQuery(
            user_id="u1", query="dark mode UI preference", limit=5,
        ))
        assert len(results) > 0
        # Dark mode memory should rank first
        assert "dark mode" in results[0].content.lower()

    def test_min_relevance_filter(self) -> None:
        """min_relevance filters out low-scoring results."""
        store = InMemoryStore()
        store.store("u1", "Python programming language")
        store.store("u1", "Completely unrelated content about cooking")
        results = store.retrieve(MemoryQuery(
            user_id="u1", query="Python programming", min_relevance=0.5, limit=10,
        ))
        # Only the Python memory should pass the threshold
        for r in results:
            assert r.relevance_score >= 0.5

    def test_empty_store_returns_empty(self) -> None:
        """Empty store returns no results."""
        store = InMemoryStore()
        results = store.retrieve(MemoryQuery(user_id="u1", query="anything"))
        assert results == []
