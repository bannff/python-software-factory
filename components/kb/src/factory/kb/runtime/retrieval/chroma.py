"""ChromaDB vector store adapter."""

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


class ChromaConfig(BaseModel):
    """Configuration for ChromaDB vector store."""
    persist_directory: str = Field(default="./chroma_data", description="Directory to persist data")
    collection_name: str = Field(default="default", description="Default collection name")
    embedding_function: str | None = Field(default=None, description="Embedding function to use")
    model_config = {"extra": "forbid"}


class ChromaVectorStore(VectorStore):
    """ChromaDB implementation of VectorStore."""

    def __init__(self, config: ChromaConfig | None = None) -> None:
        if not CHROMADB_AVAILABLE:
            raise ImportError("chromadb is not installed. Install with: pip install chromadb")
        self._config = config or ChromaConfig()
        self._client = chromadb.PersistentClient(path=self._config.persist_directory)
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


# Install legacy aliases for backwards compatibility
def _install_legacy_aliases() -> None:
    import sys
    import types

    if "kb_module" not in sys.modules:
        kb_module = types.ModuleType("kb_module")
        kb_module.__path__ = []
        sys.modules["kb_module"] = kb_module
    else:
        kb_module = sys.modules["kb_module"]

    if "kb_module.engine" not in sys.modules:
        engine = types.ModuleType("kb_module.engine")
        engine.__path__ = []
        sys.modules["kb_module.engine"] = engine
        setattr(kb_module, "engine", engine)
    else:
        engine = sys.modules["kb_module.engine"]

    if "kb_module.runtime.retrieval" not in sys.modules:
        retrieval = types.ModuleType("kb_module.runtime.retrieval")
        retrieval.__path__ = []
        sys.modules["kb_module.runtime.retrieval"] = retrieval
        setattr(engine, "retrieval", retrieval)
    else:
        retrieval = sys.modules["kb_module.runtime.retrieval"]

    sys.modules["kb_module.runtime.retrieval.chroma"] = sys.modules[__name__]
    setattr(retrieval, "chroma", sys.modules[__name__])


_install_legacy_aliases()
