"""Hypothesis property tests for KBRuntime through VectorStore ABC.

Verifies that KBRuntime operations (ingest, get, delete, list, search,
stats) behave correctly for arbitrary inputs when backed by an in-memory
VectorStore test double.  No real embeddings or external services.

Properties tested:
- ingest-then-get roundtrip preserves content
- ingest-then-delete removes the document
- delete of non-existent doc returns False
- list_documents returns all ingested docs
- list_documents respects limit parameter
- get_collection_stats counts match ingested docs
- search always returns list[SearchResult]
- all ops raise RuntimeError when no vector store is set
"""

from __future__ import annotations

import tempfile
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from factory.kb.runtime.collections import CollectionStats
from factory.kb.runtime.models import Document, IngestResult, SearchResult
from factory.kb.runtime.ports import VectorStore
from factory.kb.runtime.runtime import KBRuntime

_ids = st.text(
    min_size=1, max_size=20,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)
_content = st.text(min_size=1, max_size=200).filter(lambda s: s.strip())


class _InMemoryVectorStore(VectorStore):
    """Minimal in-memory VectorStore for property tests."""

    def __init__(self) -> None:
        self._docs: dict[str, Document] = {}

    def add(self, document: Document, **kw: Any) -> None:
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


def _make_runtime() -> tuple[KBRuntime, _InMemoryVectorStore]:
    store = _InMemoryVectorStore()
    rt = KBRuntime(tempfile.mkdtemp())
    rt.set_vector_store(store)
    return rt, store


# -- roundtrip ---------------------------------------------------------------

@settings(max_examples=50, deadline=None)
@given(doc_id=_ids, content=_content)
def test_ingest_then_get_roundtrip(doc_id: str, content: str) -> None:
    """Ingested content is retrievable by document_id."""
    rt, _ = _make_runtime()
    result = rt.ingest(content, document_id=doc_id)
    assert isinstance(result, IngestResult)
    assert result.document_id == doc_id
    doc = rt.get_document(doc_id)
    assert doc is not None
    assert doc.content == content


# -- delete semantics ---------------------------------------------------------

@settings(max_examples=50, deadline=None)
@given(doc_id=_ids, content=_content)
def test_ingest_then_delete(doc_id: str, content: str) -> None:
    """Delete returns True for existing doc, get returns None after."""
    rt, _ = _make_runtime()
    rt.ingest(content, document_id=doc_id)
    assert rt.delete_document(doc_id) is True
    assert rt.get_document(doc_id) is None


@settings(max_examples=50, deadline=None)
@given(doc_id=_ids)
def test_delete_nonexistent(doc_id: str) -> None:
    """Delete returns False for unknown document_id."""
    rt, _ = _make_runtime()
    assert rt.delete_document(doc_id) is False


# -- list_documents -----------------------------------------------------------

@settings(max_examples=50, deadline=None)
@given(ids_and_contents=st.lists(
    st.tuples(_ids, _content), min_size=1, max_size=10, unique_by=lambda t: t[0],
))
def test_list_documents_returns_all(
    ids_and_contents: list[tuple[str, str]],
) -> None:
    """list_documents returns every ingested document."""
    rt, _ = _make_runtime()
    for doc_id, content in ids_and_contents:
        rt.ingest(content, document_id=doc_id)
    docs = rt.list_documents()
    assert len(docs) == len(ids_and_contents)
    returned_ids = {d.id for d in docs}
    for doc_id, _ in ids_and_contents:
        assert doc_id in returned_ids


@settings(max_examples=50, deadline=None)
@given(contents=st.lists(_content, min_size=5, max_size=5))
def test_list_documents_limit(contents: list[str]) -> None:
    """list_documents(limit=2) returns at most 2 documents."""
    rt, _ = _make_runtime()
    for i, c in enumerate(contents):
        rt.ingest(c, document_id=f"doc{i}")
    docs = rt.list_documents(limit=2)
    assert len(docs) <= 2


# -- stats --------------------------------------------------------------------

@settings(max_examples=50, deadline=None)
@given(ids_and_contents=st.lists(
    st.tuples(_ids, _content), min_size=0, max_size=10, unique_by=lambda t: t[0],
))
def test_get_collection_stats_counts(
    ids_and_contents: list[tuple[str, str]],
) -> None:
    """get_collection_stats().document_count matches ingested count."""
    rt, _ = _make_runtime()
    for doc_id, content in ids_and_contents:
        rt.ingest(content, document_id=doc_id)
    stats = rt.get_collection_stats()
    assert isinstance(stats, CollectionStats)
    assert stats.document_count == len(ids_and_contents)


# -- search -------------------------------------------------------------------

@settings(max_examples=50, deadline=None)
@given(query=_content)
def test_search_returns_list(query: str) -> None:
    """search() never crashes and always returns list[SearchResult]."""
    rt, _ = _make_runtime()
    results = rt.search(query)
    assert isinstance(results, list)
    assert all(isinstance(r, SearchResult) for r in results)


# -- empty content rejection ---------------------------------------------------

@settings(max_examples=50, deadline=None)
@given(doc_id=_ids, content=st.one_of(st.just(""), st.text(max_size=20).filter(lambda s: not s.strip())))
def test_ingest_rejects_empty_content(doc_id: str, content: str) -> None:
    """Ingest rejects empty or whitespace-only content with status 'rejected'."""
    rt, _ = _make_runtime()
    result = rt.ingest(content, document_id=doc_id)
    assert result.status == "rejected"
    assert result.chunks_created == 0
    assert rt.get_document(doc_id) is None


# -- no vector store ----------------------------------------------------------

def test_no_vector_store_raises() -> None:
    """All ops raise RuntimeError when no vector store is set."""
    rt = KBRuntime(tempfile.mkdtemp())
    import pytest

    with pytest.raises(RuntimeError):
        rt.ingest("hello")
    with pytest.raises(RuntimeError):
        rt.get_document("x")
    with pytest.raises(RuntimeError):
        rt.delete_document("x")
    with pytest.raises(RuntimeError):
        rt.list_documents()
    with pytest.raises(RuntimeError):
        rt.get_collection_stats()
    with pytest.raises(RuntimeError):
        rt.search("q")
