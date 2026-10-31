"""Tests for evolution integration in Neo4jEmbeddingMemoryStore.

Covers: store with/without LLM, health_check evolution status,
lazy engine init, and evolution constraint creation.
All Neo4j and LLM interactions are mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from factory.memory.runtime.models import Memory, MemoryHealth


# ── Helpers ──────────────────────────────────────────────────────────

def _mock_driver():
    """Return a mock Neo4j driver with session context manager."""
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)
    return driver, session


def _mock_embedder(dims: int = 384):
    embedder = MagicMock()
    embedder.dimensions = dims
    embedder.embed.return_value = [[0.1] * dims]
    return embedder


def _make_base(driver, session):
    """Create a mock Neo4jMemoryStore base."""
    base = MagicMock()
    base.driver = driver
    base.database = "testdb"
    base.store.return_value = Memory(
        id="mem-1", user_id="u1", content="test content",
    )
    base.health_check.return_value = MemoryHealth(
        healthy=True, backend="neo4j", message="Neo4j connected",
    )
    return base


def _build_store(llm_complete=None):
    """Build a Neo4jEmbeddingMemoryStore with all deps mocked."""
    driver, session = _mock_driver()
    base = _make_base(driver, session)
    embedder = _mock_embedder()
    with patch(
        "factory.memory.runtime.adapters.neo4j_embedding.Neo4jEmbeddingMemoryStore"
        "._ensure_vector_index"
    ), patch(
        "factory.memory.runtime.adapters.neo4j_embedding.Neo4jEmbeddingMemoryStore"
        "._ensure_evolution_constraints"
    ):
        from factory.memory.runtime.adapters.neo4j_embedding import (
            Neo4jEmbeddingMemoryStore,
        )
        store = Neo4jEmbeddingMemoryStore(base, embedder, llm_complete)
    return store, driver, session, base


# ── store() evolution integration ────────────────────────────────────

class TestStoreEvolution:
    def test_store_without_llm_skips_evolution(self) -> None:
        store, _, _, base = _build_store(llm_complete=None)
        result = store.store("u1", "hello")
        base.store.assert_called_once()
        assert result.id == "mem-1"

    @patch("factory.memory.runtime.adapters.neo4j_evolution.set_evolution_properties")
    @patch("factory.memory.runtime.adapters.neo4j_evolution.run_content_analysis")
    def test_store_with_llm_triggers_analysis(self, mock_rca, mock_sep) -> None:
        llm = MagicMock()
        mock_rca.return_value = {"keywords": ["k"], "context": "c", "tags": ["t"]}
        store, _, _, _ = _build_store(llm_complete=llm)
        store.store("u1", "hello")
        mock_rca.assert_called_once_with(llm, "hello")
        mock_sep.assert_called_once()

    @patch("factory.memory.runtime.adapters.neo4j_evolution.evolve")
    @patch("factory.memory.runtime.adapters.neo4j_evolution.set_evolution_properties")
    @patch("factory.memory.runtime.adapters.neo4j_evolution.run_content_analysis")
    def test_store_with_llm_runs_evolution(self, mock_rca, mock_sep, mock_evolve) -> None:
        llm = MagicMock()
        mock_rca.return_value = {"keywords": [], "context": "", "tags": []}
        store, driver, session, _ = _build_store(llm_complete=llm)
        # Simulate existing memories so _run_evolution proceeds
        rec = MagicMock()
        rec.__getitem__ = lambda self, k: 3
        session.run.return_value.single.return_value = rec
        store._run_evolution(store._get_engine(), store._base.store.return_value, {})
        mock_evolve.assert_called_once()


# ── _get_engine lazy init ────────────────────────────────────────────

class TestGetEngine:
    def test_returns_none_without_llm(self) -> None:
        store, _, _, _ = _build_store(llm_complete=None)
        assert store._get_engine() is None

    def test_returns_engine_with_llm(self) -> None:
        store, _, _, _ = _build_store(llm_complete=MagicMock())
        engine = store._get_engine()
        assert engine is not None

    def test_engine_is_cached(self) -> None:
        store, _, _, _ = _build_store(llm_complete=MagicMock())
        e1 = store._get_engine()
        e2 = store._get_engine()
        assert e1 is e2


# ── health_check ─────────────────────────────────────────────────────

class TestHealthCheck:
    def test_reports_evolution_enabled(self) -> None:
        store, _, _, _ = _build_store(llm_complete=MagicMock())
        health = store.health_check()
        assert "evolution: enabled" in health.message

    def test_reports_evolution_disabled(self) -> None:
        store, _, _, _ = _build_store(llm_complete=None)
        health = store.health_check()
        assert "evolution: disabled" in health.message

    def test_unhealthy_skips_evolution_message(self) -> None:
        store, _, _, base = _build_store(llm_complete=MagicMock())
        base.health_check.return_value = MemoryHealth(
            healthy=False, backend="neo4j", message="Connection refused",
        )
        health = store.health_check()
        assert "Connection refused" in health.message


# ── _run_evolution edge cases ────────────────────────────────────────

class TestRunEvolutionEdgeCases:
    @patch("factory.memory.runtime.adapters.neo4j_evolution.evolve")
    def test_skips_when_no_other_memories(self, mock_evolve) -> None:
        store, _, session, _ = _build_store(llm_complete=MagicMock())
        rec = MagicMock()
        rec.__getitem__ = lambda self, k: 0
        session.run.return_value.single.return_value = rec
        mem = Memory(id="mem-1", user_id="u1", content="hello")
        store._run_evolution(store._get_engine(), mem, {})
        mock_evolve.assert_not_called()

    @patch("factory.memory.runtime.adapters.neo4j_evolution.evolve")
    def test_skips_when_count_query_returns_none(self, mock_evolve) -> None:
        store, _, session, _ = _build_store(llm_complete=MagicMock())
        session.run.return_value.single.return_value = None
        mem = Memory(id="mem-1", user_id="u1", content="hello")
        store._run_evolution(store._get_engine(), mem, {})
        mock_evolve.assert_not_called()
