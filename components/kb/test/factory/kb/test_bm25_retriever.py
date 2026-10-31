"""Tests for BM25Retriever adapter (rank-bm25 library).

Exercises the real BM25Plus algorithm — no mocks.
"""

from __future__ import annotations

from typing import Any

import pytest

from factory.kb.runtime.models import Document, SearchResult
from factory.kb.runtime.ports import VectorStore
from factory.kb.runtime.retrieval.bm25_retriever import BM25Retriever


class _InMemoryVectorStore(VectorStore):
    """Minimal in-memory vector store for testing retrievers."""

    def __init__(self) -> None:
        self._docs: dict[str, Document] = {}

    def add(self, document: Document, **kwargs: Any) -> None:
        self._docs[document.id] = document

    def search(self, query: str, limit: int = 10,
               filters: dict[str, Any] | None = None) -> list[SearchResult]:
        return []

    def delete(self, document_id: str) -> bool:
        return self._docs.pop(document_id, None) is not None

    def get(self, document_id: str) -> Document | None:
        return self._docs.get(document_id)

    def list_documents(self, limit: int = 100) -> list[Document]:
        return list(self._docs.values())[:limit]


@pytest.fixture
def store() -> _InMemoryVectorStore:
    s = _InMemoryVectorStore()
    s.add(Document(id="d1", content="Python is a great programming language"))
    s.add(Document(id="d2", content="Java and JavaScript are different languages"))
    s.add(Document(id="d3", content="Machine learning uses Python extensively"))
    s.add(Document(id="d4", content="The weather today is sunny and warm"))
    return s


class TestBM25Retriever:
    """Tests for BM25Retriever using real rank-bm25 library."""

    def test_import(self) -> None:
        """BM25Retriever and rank_bm25 are importable."""
        from rank_bm25 import BM25Plus
        assert BM25Plus is not None
        assert BM25Retriever is not None

    def test_instantiation(self, store: _InMemoryVectorStore) -> None:
        """Can construct a BM25Retriever with a vector store."""
        retriever = BM25Retriever(store)
        assert retriever is not None

    def test_retrieve_returns_results(self, store: _InMemoryVectorStore) -> None:
        """Querying returns ranked SearchResult objects."""
        retriever = BM25Retriever(store)
        results = retriever.retrieve("Python programming")
        assert len(results) > 0
        assert all(isinstance(r, SearchResult) for r in results)

    def test_ranking_relevance(self, store: _InMemoryVectorStore) -> None:
        """Python-related docs rank higher for a Python query."""
        retriever = BM25Retriever(store)
        results = retriever.retrieve("Python programming language")
        ids = [r.document_id for r in results]
        # d1 ("Python is a great programming language") should rank first
        assert ids[0] == "d1"
        # d3 ("Machine learning uses Python extensively") should also appear
        assert "d3" in ids

    def test_irrelevant_query_low_results(self, store: _InMemoryVectorStore) -> None:
        """Query with no matching terms returns fewer/no results."""
        retriever = BM25Retriever(store)
        results = retriever.retrieve("quantum physics relativity")
        # BM25 may return 0 results if no terms match
        assert len(results) == 0

    def test_scores_are_normalized(self, store: _InMemoryVectorStore) -> None:
        """Scores should be between 0 and 1."""
        retriever = BM25Retriever(store)
        results = retriever.retrieve("Python")
        for r in results:
            assert 0.0 <= r.score <= 1.0

    def test_limit_parameter(self, store: _InMemoryVectorStore) -> None:
        """Limit caps the number of results."""
        retriever = BM25Retriever(store)
        results = retriever.retrieve("language", limit=1)
        assert len(results) <= 1

    def test_empty_corpus(self) -> None:
        """Empty store returns empty results."""
        empty = _InMemoryVectorStore()
        retriever = BM25Retriever(empty)
        results = retriever.retrieve("anything")
        assert results == []

    def test_single_document_corpus(self) -> None:
        """BM25Plus handles single-document corpus (no negative scores)."""
        s = _InMemoryVectorStore()
        s.add(Document(id="only", content="The only document about cats"))
        retriever = BM25Retriever(s)
        results = retriever.retrieve("cats")
        assert len(results) >= 1
        assert results[0].score > 0

    def test_result_metadata_preserved(self) -> None:
        """Metadata from documents is carried through to results."""
        s = _InMemoryVectorStore()
        s.add(Document(id="m1", content="Test document", metadata={"tag": "test"}))
        retriever = BM25Retriever(s)
        results = retriever.retrieve("test document")
        assert len(results) > 0
        assert results[0].metadata.get("tag") == "test"
