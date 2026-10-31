import pytest
import yaml
from factory.kb.runtime.models import Document, SearchResult
from factory.kb.runtime.ports import VectorStore
from factory.kb.runtime.runtime import KBRuntime
from typing import Any


class _InMemoryVectorStore(VectorStore):
    """Minimal in-memory vector store for unit tests."""

    def __init__(self) -> None:
        self._docs: dict[str, Document] = {}

    def add(self, document: Document, **kwargs: Any) -> None:
        self._docs[document.id] = document

    def search(self, query: str, limit: int = 10,
               filters: dict[str, Any] | None = None) -> list[SearchResult]:
        results = []
        for doc in self._docs.values():
            if query.lower() in doc.content.lower():
                results.append(SearchResult(
                    document_id=doc.id, content=doc.content[:500],
                    score=0.5, metadata=doc.metadata,
                ))
        return results[:limit]

    def delete(self, document_id: str) -> bool:
        return self._docs.pop(document_id, None) is not None

    def get(self, document_id: str) -> Document | None:
        return self._docs.get(document_id)

    def list_documents(self, limit: int = 100) -> list[Document]:
        return list(self._docs.values())[:limit]


@pytest.fixture
def config_dir(tmp_path):
    conf = tmp_path / "config"
    conf.mkdir()
    collections_dir = conf / "collections"
    collections_dir.mkdir()

    # Create a sample collection config
    collection_config = {
        "id": "test-collection",
        "name": "Test Collection",
        "description": "A test collection",
        "embedding_model": "default",
    }
    with open(collections_dir / "test.yaml", "w") as f:
        yaml.dump(collection_config, f)

    return conf


def test_runtime_loading(config_dir):
    """Test runtime initialization and collection loading."""
    runtime = KBRuntime(str(config_dir))
    
    # Check that collections were loaded
    registry = runtime.get_collection_registry()
    collections = registry.list_all()
    assert len(collections) == 1
    assert collections[0].id == "test-collection"


def test_runtime_operations(tmp_path):
    """Test basic runtime operations."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    runtime = KBRuntime(str(config_dir))
    runtime.set_vector_store(_InMemoryVectorStore())
    
    # Test ingestion
    result = runtime.ingest(
        content="Test content",
        metadata={"title": "Test Document"},
    )
    assert result.document_id is not None
    assert result.status == "ingested"
    
    # Test retrieval
    doc = runtime.get_document(result.document_id)
    assert doc is not None
    assert doc.content == "Test content"
    
    # Test search
    results = runtime.search("Test")
    assert len(results) > 0
    
    # Test deletion
    deleted = runtime.delete_document(result.document_id)
    assert deleted is True
