"""Recipe-driven tests for KB Graph Search — graph-enriched semantic search.

Mirrors `.agents/recipes/kb-graph-search.md` steps:
vector search → text fallback (exception) → text fallback (empty) →
graph enrichment → enrichment Cypher → backfill → NoOp backfill → SearchResult fields.

All mock-based — no real Neo4j or LLM required.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from factory.kb.runtime.models import SearchResult
from factory.kb.runtime.retrieval.neo4j_embedding import NoOpKBEmbedder
from factory.kb.runtime.retrieval.neo4j_vector import Neo4jVectorConfig, Neo4jVectorStore


class _FixedEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]

    @property
    def dimensions(self) -> int:
        return 4


class _FailingEmbedder:
    """Embedder that always raises — forces text fallback."""
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Embedding service unavailable")

    @property
    def dimensions(self) -> int:
        return 4


def _session() -> MagicMock:
    s = MagicMock()
    s.run = MagicMock(return_value=[])
    s.__enter__ = lambda s: s
    s.__exit__ = MagicMock(return_value=False)
    return s


def _store(embedder: Any = None, cfg: Neo4jVectorConfig | None = None) -> Neo4jVectorStore:
    driver = MagicMock()
    driver.session.return_value = _session()
    with patch("factory.kb.runtime.retrieval.neo4j_vector.GraphDatabase") as gd:
        gd.driver.return_value = driver
        store = Neo4jVectorStore(
            config=cfg or Neo4jVectorConfig(extract_entities=False),
            embedder=embedder or _FixedEmbedder(),
        )
    store._driver = driver
    return store


def _rec(**fields: Any) -> MagicMock:
    r = MagicMock()
    r.__getitem__ = lambda _, k: fields[k]
    r.keys = lambda: list(fields.keys())
    return r


# -- Step 1: Vector search returns results ---------------------------------

def test_vector_search_returns_results() -> None:
    store = _store()
    node = {"id": "doc-1", "content": "hello world", "meta_src": "test"}
    store._run = MagicMock(return_value=[_rec(id="doc-1", content="hello world", score=0.95, node=node)])
    results = store.search("hello", limit=5)
    assert len(results) == 1
    assert isinstance(results[0], SearchResult)
    assert results[0].document_id == "doc-1"
    assert results[0].score == pytest.approx(0.95)


# -- Step 2: Text fallback when vector fails (exception) -------------------

def test_text_fallback_on_embed_exception() -> None:
    store = _store(embedder=_FailingEmbedder())
    node = {"id": "doc-1", "content": "Polylith monorepo"}
    store._run = MagicMock(return_value=[_rec(id="doc-1", content="Polylith monorepo", score=0.5, node=node)])
    results = store.search("Polylith")
    assert len(results) >= 1
    assert results[0].score == pytest.approx(0.5)


# -- Step 3: Text fallback when vector returns empty -----------------------

def test_text_fallback_on_empty_vector_results() -> None:
    store = _store()
    node = {"id": "doc-2", "content": "MCP interface"}

    def _side_effect(cypher: str, **kw: Any) -> list[Any]:
        if "vector.queryNodes" in cypher:
            return []
        return [_rec(id="doc-2", content="MCP interface", score=0.5, node=node)]

    store._run = _side_effect
    results = store.search("MCP")
    assert len(results) == 1
    assert results[0].document_id == "doc-2"
    assert results[0].score == pytest.approx(0.5)


# -- Step 4: Graph enrichment adds graph_context to metadata ---------------

def test_graph_enrichment_adds_context() -> None:
    store = _store()
    node = {"id": "doc-1", "content": "test"}
    vec_rec = _rec(id="doc-1", content="test", score=0.9, node=node)
    graph_rec = _rec(rt="HAS_ENTITY", lb=["__Entity__"], mid="ent-1")

    def _side_effect(cypher: str, **kw: Any) -> list[Any]:
        if "vector.queryNodes" in cypher:
            return [vec_rec]
        if "-[r]-" in cypher:
            return [graph_rec]
        return []

    store._run = _side_effect
    results = store.search("test", include_graph_context=True)
    assert len(results) == 1
    ctx = results[0].metadata.get("graph_context")
    assert ctx is not None
    assert ctx[0]["relationship"] == "HAS_ENTITY"
    assert ctx[0]["id"] == "ent-1"


# -- Step 5: Graph enrichment Cypher uses undirected pattern ---------------

def test_graph_enrichment_cypher_pattern() -> None:
    store = _store()
    captured: list[str] = []
    store._run = lambda cypher, **kw: (captured.append(cypher), [])[1]
    sr = SearchResult(document_id="doc-1", content="x", score=0.9, metadata={})
    store._enrich_graph_context([sr])
    graph_q = [c for c in captured if "-[r]-" in c]
    assert graph_q, "Must use undirected -[r]- pattern"
    assert "LIMIT 5" in graph_q[0]


# -- Step 6: Backfill embeddings -------------------------------------------

def test_backfill_embeddings_calls_set_embedding() -> None:
    store = _store()
    null_doc = _rec(id="doc-1", content="needs embedding")
    set_count = {"n": 0}

    def _side_effect(cypher: str, **kw: Any) -> list[Any]:
        if "IS NULL" in cypher:
            return [null_doc]
        if "SET" in cypher and "embedding" in cypher:
            set_count["n"] += 1
        return []

    store._run = _side_effect
    assert store.backfill_embeddings() == 1
    assert set_count["n"] == 1


# -- Step 7: Backfill with NoOp embedder returns 0 immediately -------------

def test_backfill_noop_embedder_returns_zero() -> None:
    assert _store(embedder=NoOpKBEmbedder()).backfill_embeddings() == 0


# -- Step 8: SearchResult fields populated correctly -----------------------

def test_search_result_fields() -> None:
    sr = SearchResult(document_id="doc-42", content="The answer", score=0.87,
                      metadata={"source": "hitchhiker"})
    assert sr.document_id == "doc-42"
    assert sr.content == "The answer"
    assert sr.score == pytest.approx(0.87)
    assert sr.metadata == {"source": "hitchhiker"}


def test_search_result_metadata_defaults_to_empty_dict() -> None:
    assert SearchResult(document_id="d", content="c", score=0.5).metadata == {}


def test_search_result_metadata_none_coerced() -> None:
    assert SearchResult(document_id="d", content="c", score=0.5, metadata=None).metadata == {}
