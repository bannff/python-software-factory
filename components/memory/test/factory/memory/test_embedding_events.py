"""Integration tests for event emission in neo4j_embedding.py.

Mocks both Neo4j driver AND tool_invoker to verify correct events
are emitted at each point: store, evolve.success, evolve.failed,
retrieve (vector + text_fallback), embed.failed.
"""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

from factory.memory.runtime.models import Memory, MemoryQuery


class _FakeNode(dict):
    """Dict subclass that behaves like a Neo4j node for to_memory."""


def _mock_driver():
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)
    return driver, session


def _build_store(llm_complete=None):
    driver, session = _mock_driver()
    base = MagicMock()
    base.driver = driver
    base.database = "testdb"
    base.store.return_value = Memory(id="m1", user_id="u1", content="c")
    embedder = MagicMock()
    embedder.dimensions = 384
    embedder.embed.return_value = [[0.1] * 384]
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
        store = Neo4jEmbeddingMemoryStore(base, embedder, llm_complete)
    return store, driver, session, base, embedder


@patch("factory.memory.runtime.adapters.neo4j_embedding.emit_memory_event")
class TestStoreEvents:
    def test_emits_memory_store(self, mock_emit):
        store, *_ = _build_store(llm_complete=None)
        store.store("u1", "hello", category="fact", memory_type="long_term")
        store_calls = [c for c in mock_emit.call_args_list
                       if c[0][0] == "memory.store"]
        assert len(store_calls) == 1
        payload = store_calls[0][0][1]
        assert payload["memory_id"] == "m1"
        assert payload["category"] == "fact"
        assert payload["memory_type"] == "long_term"

    @patch("factory.memory.runtime.adapters.neo4j_evolution.analyze_content")
    @patch("factory.memory.runtime.adapters.neo4j_evolution.set_evolution_properties")
    def test_emits_evolve_success(self, _sep, mock_ac, mock_emit):
        mock_ac.return_value = {"keywords": ["k"], "context": "Tech", "tags": ["t"]}
        store, _, session, _, _ = _build_store(llm_complete=MagicMock())
        rec = MagicMock()
        rec.__getitem__ = lambda s, k: 0
        session.run.return_value.single.return_value = rec
        store.store("u1", "hello")
        success_calls = [c for c in mock_emit.call_args_list
                         if c[0][0] == "memory.evolve.success"]
        assert len(success_calls) == 1
        assert success_calls[0][0][1]["memory_id"] == "m1"

    @patch("factory.memory.runtime.adapters.neo4j_evolution.analyze_content")
    @patch("factory.memory.runtime.adapters.neo4j_evolution.set_evolution_properties")
    def test_emits_evolve_failed_on_fallback(self, _sep, mock_ac, mock_emit):
        mock_ac.return_value = {"keywords": [], "context": "General", "tags": []}
        store, *_ = _build_store(llm_complete=MagicMock())
        store.store("u1", "hello")
        failed_calls = [c for c in mock_emit.call_args_list
                        if c[0][0] == "memory.evolve.failed"]
        assert len(failed_calls) == 1
        assert "llm_fallback" in str(failed_calls[0])


@patch("factory.memory.runtime.adapters.neo4j_embedding.emit_memory_event")
class TestRetrieveEvents:
    def test_emits_retrieve_vector(self, mock_emit):
        store, _, session, _, _ = _build_store()
        node = _FakeNode(
            id="m1", user_id="u1", content="c",
            created_at="2024-01-01T00:00:00+00:00",
        )
        session.run.return_value = [{"m": node, "score": 0.9}]
        q = MemoryQuery(query="test", user_id="u1", limit=5, min_relevance=0.0)
        store.retrieve(q)
        ret_calls = [c for c in mock_emit.call_args_list
                     if c[0][0] == "memory.retrieve"]
        assert len(ret_calls) == 1
        assert ret_calls[0][0][1]["method"] == "vector"

    def test_emits_retrieve_text_fallback(self, mock_emit):
        store, _, _, base, embedder = _build_store()
        embedder.embed.side_effect = RuntimeError("embed fail")
        base.retrieve.return_value = []
        q = MemoryQuery(query="test", user_id="u1", limit=5, min_relevance=0.0)
        store.retrieve(q)
        ret_calls = [c for c in mock_emit.call_args_list
                     if c[0][0] == "memory.retrieve"]
        assert len(ret_calls) == 1
        assert ret_calls[0][0][1]["method"] == "text_fallback"


@patch("factory.memory.runtime.adapters.neo4j_embedding.emit_memory_event")
class TestEmbedFailedEvent:
    def test_emits_embed_failed(self, mock_emit):
        store, _, _, _, embedder = _build_store()
        embedder.embed.side_effect = RuntimeError("GPU OOM")
        store._embed_and_set("m1", "content")
        failed_calls = [c for c in mock_emit.call_args_list
                        if c[0][0] == "memory.embed.failed"]
        assert len(failed_calls) == 1
        assert "GPU OOM" in failed_calls[0][0][1]["error"]
