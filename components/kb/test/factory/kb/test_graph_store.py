"""M7.7 Slice 1 (KB half) — KBGraphVectorStore: VectorStore over the shared graph brick.

Runs against ``GraphRuntime.get_graph("networkx")`` (the plain, non-durable
backend) for fast hermetic isolation, mirroring
``components/memory/test/factory/memory/test_graph_store.py``.
"""
from __future__ import annotations

from factory.graph.interface import GraphRuntime
from factory.kb.runtime.models import Document
from factory.kb.runtime.retrieval.embedding_local import LocalKBEmbedder
from factory.kb.runtime.retrieval.graph import KBGraphVectorStore


def _store(embedder=None) -> KBGraphVectorStore:
    return KBGraphVectorStore(
        runtime=GraphRuntime(), embedder=embedder or LocalKBEmbedder(model_path=""), backend="networkx",
    )


def test_add_then_get_roundtrip() -> None:
    store = _store()
    store.add(Document(id="doc-1", content="hello graph kb", source="unit-test"))
    fetched = store.get("doc-1")
    assert fetched is not None
    assert fetched.content == "hello graph kb"
    assert fetched.source == "unit-test"


def test_list_documents_returns_all_up_to_limit() -> None:
    store = _store()
    store.add(Document(id="doc-1", content="a"))
    store.add(Document(id="doc-2", content="b"))
    listed = store.list_documents(limit=10)
    assert {d.id for d in listed} == {"doc-1", "doc-2"}


def test_delete_removes_the_document() -> None:
    store = _store()
    store.add(Document(id="doc-1", content="temp"))
    assert store.delete("doc-1") is True
    assert store.get("doc-1") is None
    assert store.delete("doc-1") is False


def test_search_falls_back_to_text_match_without_semantic_embedder() -> None:
    store = _store()
    store.add(Document(id="doc-1", content="Prefers Dark Mode"))
    store.add(Document(id="doc-2", content="unrelated content"))
    hits = store.search("dark mode")
    assert len(hits) == 1
    assert hits[0].document_id == "doc-1"
    assert hits[0].score == 0.5


def test_search_uses_persisted_vectors_when_semantic() -> None:
    class FakeSemanticEmbedder:
        is_semantic = True

        def embed(self, texts):
            return [[1.0, 0.0] for _ in texts]

    store = _store(embedder=FakeSemanticEmbedder())
    store.add(Document(id="doc-1", content="alpha"))
    store.add(Document(id="doc-2", content="unrelated"))
    hits = store.search("alpha again")
    assert len(hits) >= 1
    assert hits[0].document_id == "doc-1"
    assert hits[0].score > 0.9


def test_metadata_round_trips_through_meta_prefixed_properties() -> None:
    store = _store()
    store.add(Document(id="doc-1", content="x", metadata={"tag": "important"}))
    fetched = store.get("doc-1")
    assert fetched is not None
    assert fetched.metadata == {"tag": "important"}
