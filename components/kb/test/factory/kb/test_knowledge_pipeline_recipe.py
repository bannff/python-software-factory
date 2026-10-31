"""Recipe-driven integration tests for the KB brick's RAG pipeline.

Mirrors the steps in `.agents/recipes/knowledge-pipeline.md`:
init → health check → ingest → search (BM25 fallback) → get → list → delete → stats.

No external services required — uses an in-memory VectorStore that forces
BM25 fallback by returning [] from search().
"""

from __future__ import annotations

import tempfile
from typing import Any

import pytest

from factory.kb.runtime.collections import CollectionStats
from factory.kb.runtime.models import Document, IngestResult, SearchResult
from factory.kb.runtime.ports import VectorStore
from factory.kb.runtime.runtime import KBRuntime

DOC_CONTENT = (
    "The Python Software Factory is a Polylith monorepo built for AI agents. "
    "Every brick exposes an MCP interface."
)
DOC_META = {"source": "readme", "type": "documentation"}


class _InMemoryVectorStore(VectorStore):
    """Minimal in-memory VectorStore — search() returns [] to force BM25."""

    def __init__(self) -> None:
        self._docs: dict[str, Document] = {}

    def add(self, document: Document, **kw: Any) -> None:
        self._docs[document.id] = document

    def search(
        self, query: str, limit: int = 10, filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        return []  # forces BM25 fallback

    def delete(self, document_id: str) -> bool:
        return self._docs.pop(document_id, None) is not None

    def get(self, document_id: str) -> Document | None:
        return self._docs.get(document_id)

    def list_documents(self, limit: int = 100) -> list[Document]:
        return list(self._docs.values())[:limit]


@pytest.fixture()
def kb() -> KBRuntime:
    """Recipe Step 1: initialise KBRuntime with in-memory vector store."""
    rt = KBRuntime(config_dir=tempfile.mkdtemp())
    rt.set_vector_store(_InMemoryVectorStore())
    return rt


# -- Step 1: Initialize ------------------------------------------------------

def test_init_runtime() -> None:
    """KBRuntime initialises with a tempdir and accepts a vector store."""
    rt = KBRuntime(config_dir=tempfile.mkdtemp())
    rt.set_vector_store(_InMemoryVectorStore())
    # Runtime is usable — stats call should not raise
    rt.get_collection_stats()


# -- Step 2: Health check / stats -------------------------------------------

def test_health_check_stats(kb: KBRuntime) -> None:
    """Fresh runtime reports CollectionStats with document_count=0."""
    stats = kb.get_collection_stats()
    assert isinstance(stats, CollectionStats)
    assert stats.document_count == 0
    assert stats.collection_id == "default"


# -- Step 3: Ingest ----------------------------------------------------------

def test_ingest_document(kb: KBRuntime) -> None:
    """Ingest returns IngestResult with correct id and status."""
    result = kb.ingest(
        content=DOC_CONTENT, metadata=DOC_META,
        source="recipe-test", document_id="doc-001",
    )
    assert isinstance(result, IngestResult)
    assert result.document_id == "doc-001"
    assert result.status == "ingested"
    assert result.chunks_created >= 1


# -- Step 4: Search (BM25 fallback) -----------------------------------------

def test_search_returns_results(kb: KBRuntime) -> None:
    """Search falls back to BM25 when vector search returns []."""
    kb.ingest(content=DOC_CONTENT, document_id="doc-001")
    results = kb.search(query="Python Software Factory", limit=3)
    assert isinstance(results, list)
    assert all(isinstance(r, SearchResult) for r in results)
    assert len(results) >= 1
    assert results[0].document_id == "doc-001"


# -- Step 5: Get document roundtrip ------------------------------------------

def test_get_document_roundtrip(kb: KBRuntime) -> None:
    """Ingested document is retrievable by ID with matching content."""
    kb.ingest(content=DOC_CONTENT, document_id="doc-001")
    doc = kb.get_document("doc-001")
    assert doc is not None
    assert isinstance(doc, Document)
    assert doc.content == DOC_CONTENT


# -- Step 6: List documents --------------------------------------------------

def test_list_documents(kb: KBRuntime) -> None:
    """Ingesting multiple docs makes them all appear in list_documents."""
    for i in range(3):
        kb.ingest(content=f"Document {i}", document_id=f"doc-{i:03d}")
    docs = kb.list_documents()
    assert len(docs) == 3
    ids = {d.id for d in docs}
    assert ids == {"doc-000", "doc-001", "doc-002"}


# -- Step 7: Delete ----------------------------------------------------------

def test_delete_document(kb: KBRuntime) -> None:
    """Deleted document is no longer retrievable."""
    kb.ingest(content=DOC_CONTENT, document_id="doc-001")
    assert kb.delete_document("doc-001") is True
    assert kb.get_document("doc-001") is None


# -- Step 8: Stats after operations ------------------------------------------

def test_stats_after_operations(kb: KBRuntime) -> None:
    """Stats track document count through ingest and delete."""
    for i in range(3):
        kb.ingest(content=f"Doc {i}", document_id=f"doc-{i}")
    assert kb.get_collection_stats().document_count == 3

    kb.delete_document("doc-1")
    assert kb.get_collection_stats().document_count == 2


# -- Step 9: Full pipeline walkthrough ---------------------------------------

def test_full_pipeline_walkthrough() -> None:
    """End-to-end recipe: init → stats → ingest → search → get → list → delete."""
    # 1. Init
    rt = KBRuntime(config_dir=tempfile.mkdtemp())
    rt.set_vector_store(_InMemoryVectorStore())

    # 2. Stats — empty
    stats = rt.get_collection_stats()
    assert stats.document_count == 0

    # 3. Ingest
    result = rt.ingest(
        content=DOC_CONTENT, metadata=DOC_META,
        source="recipe-test", document_id="doc-001",
    )
    assert result.status == "ingested"

    # 4. Search (BM25 fallback)
    results = rt.search(query="Polylith monorepo", limit=3)
    assert len(results) >= 1
    assert results[0].document_id == "doc-001"

    # 5. Get document
    doc = rt.get_document("doc-001")
    assert doc is not None and doc.content == DOC_CONTENT

    # 6. List documents
    docs = rt.list_documents()
    assert len(docs) == 1

    # 7. Stats — 1 doc
    assert rt.get_collection_stats().document_count == 1

    # 8. Delete
    assert rt.delete_document("doc-001") is True

    # 9. Verify gone
    assert rt.get_document("doc-001") is None

    # 10. Stats — back to 0
    assert rt.get_collection_stats().document_count == 0
