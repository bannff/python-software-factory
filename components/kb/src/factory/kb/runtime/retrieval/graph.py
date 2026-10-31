"""Graph-backed KB document storage (M7.7 Unified graph memory, Slice 1).

Delegates persistence to the ``graph`` brick's ``GraphRuntime`` — the SAME
shared persistent-networkx store the memory brick's ``GraphMemoryStore``
also writes into (consult `8382bf2f`: "one target is the shared graph
brick store, not a shared Protocol"). Shape mirrors ``neo4j_vector.py``
(this brick's own precedent for an adapter wrapping an external graph
runtime rather than owning storage) — vector search with a text fallback,
same as the neo4j adapter, using the same "embed once, persist the vector,
compare against stored peer vectors" discipline the memory-side adapter
was fixed to use after Gate A.5 `6edab2de` flagged the O(n²) alternative.
"""
from __future__ import annotations

from typing import Any

from factory.graph.interface import Entity, GraphRuntime

from ..models import Document, SearchResult
from ..ports import VectorStore
from .embedding_local import LocalKBEmbedder

_NODE_TYPE = "kb_document"


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na > 0 and nb > 0 else 0.0


def _entity_to_document(entity: Entity) -> Document:
    props = entity.properties
    meta = {k[5:]: v for k, v in props.items() if k.startswith("meta_")}
    return Document(
        id=entity.id, content=props.get("content", ""), metadata=meta,
        source=props.get("source") or None,
    )


class KBGraphVectorStore(VectorStore):
    """``VectorStore`` adapter over the shared graph brick's KnowledgeGraph."""

    def __init__(self, runtime: GraphRuntime | None = None,
                 embedder: LocalKBEmbedder | None = None,
                 backend: str = "persistent_networkx") -> None:
        self._graph = (runtime or GraphRuntime()).get_graph(backend)
        self._embedder = embedder or LocalKBEmbedder()

    @property
    def embedder(self) -> LocalKBEmbedder:
        """Read-only introspection for a future Embeddings status tool."""
        return self._embedder

    def add(self, document: Document, **kwargs: Any) -> Any:
        props: dict[str, Any] = {"content": document.content, "source": document.source or ""}
        if document.metadata:
            for k, v in document.metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    props[f"meta_{k}"] = v
        if self._embedder.is_semantic:
            [vector] = self._embedder.embed([document.content])
            props["embed_vector"] = vector
        self._graph.add_entity(Entity(id=document.id, type=_NODE_TYPE, properties=props))
        return None

    def search(self, query: str, limit: int = 10,
               filters: dict[str, Any] | None = None) -> list[SearchResult]:
        del filters  # no metadata filter pushdown in this reference slice
        candidates = self._graph.find_entities(entity_type=_NODE_TYPE, limit=1000)
        if self._embedder.is_semantic:
            [query_vector] = self._embedder.embed([query])
            scored = [
                (entity, _cosine(query_vector, entity.properties.get("embed_vector", [])))
                for entity in candidates
            ]
            scored = [pair for pair in scored if pair[1] > 0]
            scored.sort(key=lambda pair: pair[1], reverse=True)
            return [self._to_result(entity, score) for entity, score in scored[:limit]]
        matched = [e for e in candidates if query.lower() in e.properties.get("content", "").lower()]
        return [self._to_result(entity, 0.5) for entity in matched[:limit]]

    @staticmethod
    def _to_result(entity: Entity, score: float) -> SearchResult:
        props = entity.properties
        meta = {k[5:]: v for k, v in props.items() if k.startswith("meta_")}
        return SearchResult(
            document_id=entity.id, content=props.get("content", ""),
            score=float(score), metadata=meta,
        )

    def delete(self, document_id: str) -> bool:
        return self._graph.delete_entity(document_id)

    def get(self, document_id: str) -> Document | None:
        entity = self._graph.get_entity(document_id)
        return _entity_to_document(entity) if entity else None

    def list_documents(self, limit: int = 100) -> list[Document]:
        entities = self._graph.find_entities(entity_type=_NODE_TYPE, limit=limit)
        return [_entity_to_document(entity) for entity in entities[:limit]]


__all__ = ["KBGraphVectorStore"]
