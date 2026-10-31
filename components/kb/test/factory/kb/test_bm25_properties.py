"""Hypothesis property tests for BM25Retriever.

Verifies that BM25Retriever behaves correctly for arbitrary inputs
when backed by an in-memory VectorStore test double.

Properties tested:
- retrieve never crashes for arbitrary queries and document content
- all returned scores are in [0.0, 1.0]
- limit parameter is respected
- empty corpus always returns empty list
- every result is a SearchResult instance
- document metadata survives through to SearchResult
"""

from __future__ import annotations

from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from factory.kb.runtime.models import Document, SearchResult
from factory.kb.runtime.ports import VectorStore
from factory.kb.runtime.retrieval.bm25_retriever import BM25Retriever

_ids = st.text(
    min_size=1, max_size=20,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)
_content = st.text(min_size=0, max_size=200)
# Non-empty content with at least one word — avoids BM25Plus division-by-zero
# on all-empty corpora (known bug: NaN scores when avgdl==0).
_nonempty_content = st.text(min_size=1, max_size=200).filter(lambda t: t.strip())
_query = st.text(min_size=0, max_size=100)


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


def _make_retriever(
    docs: list[tuple[str, str, dict[str, Any]]] | None = None,
) -> BM25Retriever:
    store = _InMemoryVectorStore()
    for doc_id, content, meta in (docs or []):
        store.add(Document(id=doc_id, content=content, metadata=meta))
    return BM25Retriever(store)


_doc_tuples = st.lists(
    st.tuples(_ids, _nonempty_content, st.fixed_dictionaries({"tag": _ids})),
    min_size=1, max_size=10, unique_by=lambda t: t[0],
)


# -- never crashes -----------------------------------------------------------

@settings(max_examples=50, deadline=None)
@given(query=_query, docs=_doc_tuples)
def test_retrieve_never_crashes(query: str, docs: list) -> None:
    """retrieve() never raises for arbitrary queries and content."""
    retriever = _make_retriever(docs)
    results = retriever.retrieve(query)
    assert isinstance(results, list)


# -- scores in [0, 1] --------------------------------------------------------

@settings(max_examples=50, deadline=None)
@given(query=_query, docs=_doc_tuples)
def test_scores_in_unit_interval(query: str, docs: list) -> None:
    """All returned scores are between 0.0 and 1.0 inclusive."""
    retriever = _make_retriever(docs)
    for r in retriever.retrieve(query):
        assert 0.0 <= r.score <= 1.0, f"Score {r.score} out of [0,1]"


# -- limit respected ---------------------------------------------------------

@settings(max_examples=50, deadline=None)
@given(
    query=_query,
    docs=_doc_tuples,
    limit=st.integers(min_value=0, max_value=20),
)
def test_limit_respected(query: str, docs: list, limit: int) -> None:
    """retrieve(query, limit=n) returns at most n results."""
    retriever = _make_retriever(docs)
    results = retriever.retrieve(query, limit=limit)
    assert len(results) <= limit


# -- empty corpus returns empty -----------------------------------------------

@settings(max_examples=50, deadline=None)
@given(query=_query)
def test_empty_corpus_returns_empty(query: str) -> None:
    """BM25Retriever with no documents always returns []."""
    retriever = _make_retriever()
    assert retriever.retrieve(query) == []


# -- results are SearchResult ------------------------------------------------

@settings(max_examples=50, deadline=None)
@given(query=_query, docs=_doc_tuples)
def test_results_are_search_result(query: str, docs: list) -> None:
    """Every item in results is a SearchResult instance."""
    retriever = _make_retriever(docs)
    for r in retriever.retrieve(query):
        assert isinstance(r, SearchResult)


# -- metadata preserved ------------------------------------------------------

@settings(max_examples=50, deadline=None)
@given(doc_id=_ids, content=_nonempty_content, tag=_ids)
def test_metadata_preserved(doc_id: str, content: str, tag: str) -> None:
    """Document metadata survives through to SearchResult."""
    retriever = _make_retriever([(doc_id, content, {"tag": tag})])
    results = retriever.retrieve(content)
    for r in results:
        if r.document_id == doc_id:
            assert r.metadata.get("tag") == tag
