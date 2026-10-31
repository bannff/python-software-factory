"""Tests for evolution status tracking across store, backfill, and to_memory.

Covers: _store_with_evolution status detection, set_evolution_properties
Cypher, fetch_unevolved_memories WHERE clause, and to_memory metadata.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from factory.memory.runtime.adapters.neo4j_evolution import (
    set_evolution_properties,
)
from factory.memory.runtime.adapters.neo4j import to_memory
from factory.memory.runtime.evolve_backfill import fetch_unevolved_memories
from factory.memory.runtime.models import Memory


def _mock_driver():
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


def _build_store(llm_complete=None):
    driver, session = _mock_driver()
    base = MagicMock()
    base.driver = driver
    base.database = "testdb"
    base.store.return_value = Memory(
        id="mem-1", user_id="u1", content="test content",
    )
    with patch(
        "factory.memory.runtime.adapters.neo4j_embedding"
        ".Neo4jEmbeddingMemoryStore._ensure_vector_index"
    ), patch(
        "factory.memory.runtime.adapters.neo4j_embedding"
        ".Neo4jEmbeddingMemoryStore._ensure_evolution_constraints"
    ):
        from factory.memory.runtime.adapters.neo4j_embedding import (
            Neo4jEmbeddingMemoryStore,
        )
        store = Neo4jEmbeddingMemoryStore(base, _mock_embedder(), llm_complete)
    return store, driver, session, base


# ── _store_with_evolution status detection ───────────────────────────


class TestStoreWithEvolutionStatus:
    @patch("factory.memory.runtime.adapters.neo4j_embedding.emit_memory_event")
    @patch("factory.memory.runtime.adapters.neo4j_evolution.set_evolution_properties")
    @patch("factory.memory.runtime.adapters.neo4j_evolution.analyze_content")
    def test_good_analysis_sets_success(self, mock_ac, mock_sep, _evt):
        mock_ac.return_value = {"keywords": ["ai"], "context": "Tech", "tags": ["t"]}
        store, _, _, _ = _build_store(llm_complete=MagicMock())
        mem = Memory(id="mem-1", user_id="u1", content="hello")
        store._store_with_evolution(mem, "hello")
        _, kwargs = mock_sep.call_args
        assert kwargs.get("evolution_status") == "success"

    @patch("factory.memory.runtime.adapters.neo4j_embedding.emit_memory_event")
    @patch("factory.memory.runtime.adapters.neo4j_evolution.set_evolution_properties")
    @patch("factory.memory.runtime.adapters.neo4j_evolution.analyze_content")
    def test_fallback_analysis_sets_failed(self, mock_ac, mock_sep, _evt):
        mock_ac.return_value = {"keywords": [], "context": "General", "tags": []}
        store, _, _, _ = _build_store(llm_complete=MagicMock())
        mem = Memory(id="mem-1", user_id="u1", content="hello")
        store._store_with_evolution(mem, "hello")
        _, kwargs = mock_sep.call_args
        assert kwargs.get("evolution_status") == "failed"

    @patch("factory.memory.runtime.adapters.neo4j_embedding.emit_memory_event")
    @patch("factory.memory.runtime.adapters.neo4j_evolution.set_evolution_properties")
    @patch("factory.memory.runtime.adapters.neo4j_evolution.analyze_content")
    def test_exception_sets_failed_with_fallback(self, mock_ac, mock_sep, _evt):
        mock_ac.side_effect = RuntimeError("LLM down")
        store, _, _, _ = _build_store(llm_complete=MagicMock())
        mem = Memory(id="mem-1", user_id="u1", content="hello")
        store._store_with_evolution(mem, "hello")
        _, kwargs = mock_sep.call_args
        assert kwargs.get("evolution_status") == "failed"

    @patch("factory.memory.runtime.adapters.neo4j_embedding.emit_memory_event")
    def test_no_llm_sets_pending(self, _evt):
        store, _, session, _ = _build_store(llm_complete=None)
        store.store("u1", "hello")
        cypher_calls = [str(c) for c in session.run.call_args_list]
        assert any("evolution_status" in c for c in cypher_calls)


# ── set_evolution_properties Cypher ──────────────────────────────────


class TestSetEvolutionPropertiesCypher:
    def test_cypher_includes_evolution_status(self):
        driver, session = _mock_driver()
        set_evolution_properties(driver, "db", "m1", {"keywords": ["k"]})
        cypher = session.run.call_args[0][0]
        assert "m.evolution_status = $status" in cypher

    def test_default_status_is_success(self):
        driver, session = _mock_driver()
        set_evolution_properties(driver, "db", "m1", {})
        _, kwargs = session.run.call_args
        assert kwargs["status"] == "success"

    def test_explicit_failed_status(self):
        driver, session = _mock_driver()
        set_evolution_properties(driver, "db", "m1", {}, evolution_status="failed")
        _, kwargs = session.run.call_args
        assert kwargs["status"] == "failed"


# ── fetch_unevolved_memories WHERE clause ────────────────────────────


class TestFetchUnevolvedMemories:
    def test_matches_failed_status(self):
        driver, session = _mock_driver()
        session.run.return_value = []
        fetch_unevolved_memories(driver, "db", "u1")
        cypher = session.run.call_args[0][0]
        assert "evolution_status = 'failed'" in cypher

    def test_matches_null_status(self):
        driver, session = _mock_driver()
        session.run.return_value = []
        fetch_unevolved_memories(driver, "db", "u1")
        cypher = session.run.call_args[0][0]
        assert "evolution_status IS NULL" in cypher

    def test_specific_ids_bypass_status_filter(self):
        driver, session = _mock_driver()
        session.run.return_value = []
        fetch_unevolved_memories(driver, "db", "u1", memory_ids=["m1", "m2"])
        cypher = session.run.call_args[0][0]
        assert "evolution_status" not in cypher
        _, kwargs = session.run.call_args
        assert kwargs["ids"] == ["m1", "m2"]


# ── to_memory metadata ──────────────────────────────────────────────


class _FakeNode(dict):
    """Dict subclass that behaves like a Neo4j node for to_memory."""


class TestToMemoryMetadata:
    def test_evolution_status_in_metadata(self):
        node = _FakeNode(
            id="m1", user_id="u1", content="c",
            created_at="2024-01-01T00:00:00+00:00",
            evolution_status="success",
        )
        mem = to_memory(node)
        assert mem.metadata.get("evolution_status") == "success"

    def test_missing_evolution_status_not_in_metadata(self):
        node = _FakeNode(
            id="m1", user_id="u1", content="c",
            created_at="2024-01-01T00:00:00+00:00",
        )
        mem = to_memory(node)
        assert "evolution_status" not in mem.metadata
