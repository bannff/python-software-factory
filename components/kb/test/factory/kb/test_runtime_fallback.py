"""Tests for KBRuntime.search() BM25 fallback path.

Verifies that when the vector store returns empty results, the runtime
falls back to BM25 text search on the vector store's document list.
Also verifies that BM25 is NOT invoked when the vector store returns results.
"""

from __future__ import annotations

import tempfile
from typing import Any

from hypothesis import given, settings, strategies as st

from factory.kb.runtime.models import Document, SearchResult
from factory.kb.runtime.ports import VectorStore
from factory.kb.runtime.runtime import KBRuntime


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class _InMemoryVectorStore(VectorStore):
    """Vector store that stores docs in memory but returns empty search."""

    def __init__(self) -> None:
        self._docs: dict[str, Document] = {}
        self.search_called = False

    def add(self, document: Document, **kwargs: Any) -> None:
        self._docs[document.id] = document

    def search(self, query: str, limit: int = 10,
               filters: dict[str, Any] | None = None) -> list[SearchResult]:
        self.search_called = True
        return []

    def delete(self, document_id: str) -> bool:
        return self._docs.pop(document_id, None) is not None

    def get(self, document_id: str) -> Document | None:
        return self._docs.get(document_id)

    def list_documents(self, limit: int = 100) -> list[Document]:
        return list(self._docs.values())[:limit]


class _PopulatedVectorStore(VectorStore):
    """Vector store that returns a canned result from search."""

    def __init__(self) -> None:
        self._docs: dict[str, Document] = {}
        self.search_called = False

    def add(self, document: Document, **kwargs: Any) -> None:
        self._docs[document.id] = document

    def search(self, query: str, limit: int = 10,
               filters: dict[str, Any] | None = None) -> list[SearchResult]:
        self.search_called = True
        return [SearchResult(document_id="vec-1", content="vector hit", score=0.95)]

    def delete(self, document_id: str) -> bool:
        return self._docs.pop(document_id, None) is not None

    def get(self, document_id: str) -> Document | None:
        return self._docs.get(document_id)

    def list_documents(self, limit: int = 100) -> list[Document]:
        return list(self._docs.values())[:limit]


def _make_runtime(vector_store: VectorStore) -> KBRuntime:
    """Create a KBRuntime with a fresh temp config dir and given vector store."""
    config_dir = tempfile.mkdtemp(prefix="kb-test-")
    rt = KBRuntime(config_dir)
    rt.set_vector_store(vector_store)
    return rt


# ---------------------------------------------------------------------------
# Happy path: BM25 fallback fires when vector store returns empty
# ---------------------------------------------------------------------------

class TestSearchBM25Fallback:

    def test_fallback_returns_results_when_vector_empty(self):
        """Vector store returns [] → BM25 fallback returns results."""
        vs = _InMemoryVectorStore()
        rt = _make_runtime(vs)

        rt.ingest(content="Python is a great programming language", document_id="d1")
        results = rt.search("Python programming")

        assert vs.search_called, "vector store should have been tried first"
        assert len(results) > 0, "BM25 fallback should return results"
        assert results[0].document_id == "d1"

    def test_vector_results_bypass_bm25(self):
        """When vector store returns results, BM25 is never invoked."""
        vs = _PopulatedVectorStore()
        rt = _make_runtime(vs)

        rt.ingest(content="Some document", document_id="d1")
        results = rt.search("anything")

        assert vs.search_called
        assert len(results) == 1
        assert results[0].document_id == "vec-1"
        # BM25 retriever should never have been created
        assert rt._bm25 is None

    def test_no_vector_store_raises(self):
        """No vector store configured → RuntimeError on search."""
        config_dir = tempfile.mkdtemp(prefix="kb-test-")
        rt = KBRuntime(config_dir)

        import pytest
        with pytest.raises(RuntimeError, match="No vector store configured"):
            rt.search("anything")

    def test_fallback_empty_store_returns_empty(self):
        """BM25 fallback on empty vector store returns []."""
        vs = _InMemoryVectorStore()
        rt = _make_runtime(vs)

        results = rt.search("anything")
        assert results == []

    def test_fallback_reuses_bm25_instance(self):
        """BM25Retriever is lazily created once and reused."""
        vs = _InMemoryVectorStore()
        rt = _make_runtime(vs)

        rt.ingest(content="test doc", document_id="d1")
        rt.search("test")
        first_bm25 = rt._bm25

        rt.search("test again")
        assert rt._bm25 is first_bm25, "BM25 instance should be reused"


# ---------------------------------------------------------------------------
# Hypothesis property test: search fallback always returns a list
# ---------------------------------------------------------------------------

_query_text = st.text(min_size=0, max_size=100)
_doc_content = st.text(min_size=1, max_size=200)


@settings(max_examples=50)
@given(query=_query_text, content=_doc_content)
def test_search_fallback_always_returns_list(query: str, content: str) -> None:
    """Given arbitrary query and content, search always returns a list."""
    vs = _InMemoryVectorStore()
    rt = _make_runtime(vs)

    rt.ingest(content=content, document_id="hyp-doc")
    results = rt.search(query)

    assert isinstance(results, list), f"Expected list, got {type(results)}"
    for r in results:
        assert isinstance(r, SearchResult)
        assert isinstance(r.score, float)
