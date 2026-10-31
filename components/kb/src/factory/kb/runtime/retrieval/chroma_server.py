"""ChromaDB server-mode vector store adapter.

Uses chromadb.HttpClient to connect to a remote ChromaDB server
instead of the embedded PersistentClient. Same VectorStore protocol,
different transport.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

from pydantic import BaseModel, Field

from ..models import Document, SearchResult
from ..ports import VectorStore

try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None


class ChromaServerConfig(BaseModel):
    """Configuration for ChromaDB server-mode connection."""

    host: str = Field(default="localhost", description="ChromaDB server host")
    port: int = Field(default=8000, description="ChromaDB server port")
    ssl: bool = Field(default=False, description="Use SSL for connection")
    collection_name: str = Field(default="default", description="Default collection name")
    headers: dict[str, str] | None = Field(default=None, description="Custom headers")
    tenant: str = Field(default="default_tenant", description="Tenant name")
    database: str = Field(default="default_database", description="Database name")
    model_config = {"extra": "forbid"}


class ChromaServerVectorStore(VectorStore):
    """ChromaDB server-mode implementation of VectorStore.

    Connects to a running ChromaDB server via HTTP. Shares the same
    VectorStore protocol as ChromaVectorStore (embedded mode).
    """

    def __init__(self, config: ChromaServerConfig | None = None) -> None:
        if not CHROMADB_AVAILABLE:
            raise ImportError("chromadb is not installed. Install with: pip install chromadb")
        self._config = config or ChromaServerConfig()
        self._client = chromadb.HttpClient(
            host=self._config.host,
            port=self._config.port,
            ssl=self._config.ssl,
            headers=self._config.headers,
            tenant=self._config.tenant,
            database=self._config.database,
        )
        self._collection = self._client.get_or_create_collection(name=self._config.collection_name)

    def add(self, document: Document, **kwargs: Any) -> None:
        self._collection.add(
            ids=[document.id], documents=[document.content],
            metadatas=[document.metadata] if document.metadata else None,
        )

    def add_batch(self, documents: list[Document]) -> None:
        if not documents:
            return
        self._collection.add(
            ids=[d.id for d in documents], documents=[d.content for d in documents],
            metadatas=[d.metadata or {} for d in documents],
        )

    def search(self, query: str, limit: int = 10, filters: dict[str, Any] | None = None) -> list[SearchResult]:
        results = self._collection.query(query_texts=[query], n_results=limit, where=filters)
        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results.get("distances") else 0
                # ChromaDB L2 distance: use inverse scaling for relevance
                score = 1 / (1 + distance)
                search_results.append(SearchResult(
                    document_id=doc_id,
                    content=results["documents"][0][i] if results.get("documents") else "",
                    score=score,
                    metadata=results["metadatas"][0][i] if results.get("metadatas") else {},
                ))
        return search_results

    def get(self, document_id: str) -> Document | None:
        results = self._collection.get(ids=[document_id])
        if results["ids"]:
            return Document(
                id=results["ids"][0],
                content=results["documents"][0] if results.get("documents") else "",
                metadata=results["metadatas"][0] if results.get("metadatas") else {},
            )
        return None

    def delete(self, document_id: str) -> bool:
        try:
            self._collection.delete(ids=[document_id])
            return True
        except Exception:
            return False
    def list_documents(self, limit: int = 100) -> list[Document]:
        results = self._collection.get(limit=limit)
        ids = results.get("ids") or []
        documents = results.get("documents") or []
        metadatas = results.get("metadatas") or []
        return [
            Document(
                id=doc_id, content=documents[i] if i < len(documents) else "",
                metadata=(metadatas[i] if i < len(metadatas) else None) or {},
            )
            for i, doc_id in enumerate(ids)
        ]

    def list_collections(self) -> list[str]:
        return [c.name for c in self._client.list_collections()]

    def create_collection(self, name: str) -> None:
        self._client.get_or_create_collection(name=name)

    def delete_collection(self, name: str) -> bool:
        try:
            self._client.delete_collection(name=name)
            return True
        except Exception:
            return False

    def get_collection_stats(self, name: str | None = None) -> dict[str, Any]:
        collection_name = name or self._config.collection_name
        try:
            collection = self._client.get_collection(collection_name)
            return {"name": collection_name, "count": collection.count()}
        except Exception as e:
            return {"name": collection_name, "error": str(e)}

    def switch_collection(self, name: str) -> None:
        self._collection = self._client.get_or_create_collection(name=name)
        self._config.collection_name = name
