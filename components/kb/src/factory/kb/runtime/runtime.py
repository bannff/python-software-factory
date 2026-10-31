"""Knowledge base runtime."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

import yaml

from .collections import CollectionConfig, CollectionRegistry, CollectionStats
from .envelope import ContextEnvelope
from .models import Document, IngestResult, SearchResult
from .ports import VectorStore
from .retrieval.bm25_retriever import BM25Retriever

logger = logging.getLogger(__name__)


class KBRuntime:
    """Runtime for knowledge base operations."""

    def __init__(self, config_dir: str | Path) -> None:
        self._config_dir = Path(config_dir)
        self._vector_store: VectorStore | None = None
        self._remote_store: VectorStore | None = None
        self._bm25: BM25Retriever | None = None
        self._collection_registry = CollectionRegistry()
        self._load_config()

    def _load_config(self) -> None:
        """Load collection configurations from config directory."""
        collections_dir = self._config_dir / "collections"
        if collections_dir.exists():
            for config_file in collections_dir.glob("*.yaml"):
                try:
                    with open(config_file) as f:
                        data = yaml.safe_load(f)
                    if data:
                        config = CollectionConfig.model_validate(data)
                        self._collection_registry.register(config)
                except Exception:
                    pass

    @classmethod
    def from_config_dir(cls, config_dir: str | Path) -> KBRuntime:
        """Create runtime from config directory."""
        return cls(config_dir)

    def set_vector_store(self, vector_store: VectorStore) -> None:
        """Set the primary (local) vector store backend."""
        self._vector_store = vector_store

    def set_remote_store(self, remote_store: VectorStore) -> None:
        """Set an optional remote vector store (e.g. Bedrock KB)."""
        self._remote_store = remote_store

    def get_collection_registry(self) -> CollectionRegistry:
        """Get the collection registry."""
        return self._collection_registry

    def _require_vector_store(self) -> VectorStore:
        """Return the vector store or raise if not configured."""
        if self._vector_store is None:
            raise RuntimeError(
                "No vector store configured. Set a vector store via "
                "set_vector_store() before performing KB operations."
            )
        return self._vector_store

    def ingest(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        source: str | None = None,
        document_id: str | None = None,
        envelope: ContextEnvelope | None = None,
        extract_entities: bool | None = None,
    ) -> IngestResult:
        """Ingest a document into the knowledge base."""
        doc_id = document_id or str(uuid.uuid4())

        if not content or not content.strip():
            return IngestResult(document_id=doc_id, status="rejected", chunks_created=0)

        vs = self._require_vector_store()

        document = Document(
            id=doc_id,
            content=content,
            metadata=metadata or {},
            source=source,
        )

        extraction_result = vs.add(document, extract_entities=extract_entities)

        result = IngestResult(
            document_id=doc_id,
            status="ingested",
            chunks_created=1,
        )

        if extraction_result is not None:
            result.extraction_status = extraction_result.status
            result.entities_created = extraction_result.entities_created
            result.relationships_created = extraction_result.relationships_created
            result.extraction_message = extraction_result.message or None

        return result

    def search(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
        envelope: ContextEnvelope | None = None,
    ) -> list[SearchResult]:
        """Search the local knowledge base.

        Tries vector store first (semantic), falls back to BM25 text search
        if vector search returns no results.
        """
        vs = self._require_vector_store()
        results = vs.search(query, limit=limit, filters=filters)
        if results:
            return results

        # Fallback to BM25-ranked text search
        if self._bm25 is None:
            self._bm25 = BM25Retriever(vs)
        return self._bm25.retrieve(query, limit=limit, filters=filters)

    def search_remote(
        self,
        query: str,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search the remote knowledge base (e.g. Bedrock KB)."""
        if self._remote_store is None:
            raise RuntimeError(
                "No remote store configured. Set KB_BEDROCK_KB_ID or "
                "publish KB ID to SSM at /art/ml/bedrock/gt-kb-id."
            )
        return self._remote_store.search(query, limit=limit, filters=filters)

    def get_document(
        self,
        document_id: str,
        envelope: ContextEnvelope | None = None,
    ) -> Document | None:
        """Get a document by ID."""
        return self._require_vector_store().get(document_id)

    def delete_document(
        self,
        document_id: str,
        envelope: ContextEnvelope | None = None,
    ) -> bool:
        """Delete a document by ID."""
        return self._require_vector_store().delete(document_id)

    def list_documents(
        self,
        limit: int = 100,
        envelope: ContextEnvelope | None = None,
    ) -> list[Document]:
        """List documents in the knowledge base."""
        return self._require_vector_store().list_documents(limit=limit)

    def get_collection_stats(
        self,
        collection_id: str | None = None,
    ) -> CollectionStats:
        """Get statistics for a collection."""
        documents = self._require_vector_store().list_documents(limit=10000)
        return CollectionStats(
            collection_id=collection_id or "default",
            document_count=len(documents),
            total_size_bytes=sum(len(d.content.encode()) for d in documents),
        )
