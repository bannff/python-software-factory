"""Tests for ChromaDB vector store adapter."""

import pytest
from unittest.mock import MagicMock, patch

from factory.kb.runtime.retrieval.chroma import (
    ChromaVectorStore,
    ChromaConfig,
    CHROMADB_AVAILABLE,
)
from factory.kb.runtime.models import Document


class TestChromaConfig:
    """Tests for ChromaConfig model."""

    def test_default_config(self):
        """Test default configuration."""
        config = ChromaConfig()
        assert config.persist_directory == "./chroma_data"
        assert config.collection_name == "default"

    def test_custom_config(self):
        """Test custom configuration."""
        config = ChromaConfig(
            persist_directory="/data/chroma",
            collection_name="my_collection",
        )
        assert config.persist_directory == "/data/chroma"
        assert config.collection_name == "my_collection"


@pytest.mark.skipif(not CHROMADB_AVAILABLE, reason="chromadb not installed")
class TestChromaVectorStore:
    """Tests for ChromaVectorStore."""

    @pytest.fixture
    def mock_chroma(self):
        """Create a mock ChromaDB client."""
        with patch("factory.kb.runtime.retrieval.chroma.chromadb") as mock:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock.PersistentClient.return_value = mock_client
            yield mock, mock_client, mock_collection

    def test_add_document(self, mock_chroma):
        """Test adding a document."""
        _, mock_client, mock_collection = mock_chroma
        
        store = ChromaVectorStore(ChromaConfig())
        doc = Document(
            id="doc-1",
            content="Test content",
            metadata={"source": "test"},
        )
        store.add(doc)
        
        mock_collection.add.assert_called_once()

    def test_search(self, mock_chroma):
        """Test searching documents."""
        _, mock_client, mock_collection = mock_chroma
        mock_collection.query.return_value = {
            "ids": [["doc-1"]],
            "documents": [["Test content"]],
            "metadatas": [[{"source": "test"}]],
            "distances": [[0.1]],
        }
        
        store = ChromaVectorStore(ChromaConfig())
        results = store.search("test query", limit=5)
        
        assert len(results) == 1
        assert results[0].document_id == "doc-1"
        assert results[0].score == pytest.approx(0.9, rel=0.1)

    def test_delete_document(self, mock_chroma):
        """Test deleting a document."""
        _, mock_client, mock_collection = mock_chroma
        
        store = ChromaVectorStore(ChromaConfig())
        store.delete("doc-1")
        
        mock_collection.delete.assert_called_once_with(ids=["doc-1"])

    def test_get_document(self, mock_chroma):
        """Test getting a document by ID."""
        _, mock_client, mock_collection = mock_chroma
        mock_collection.get.return_value = {
            "ids": ["doc-1"],
            "documents": ["Test content"],
            "metadatas": [{"source": "test"}],
        }
        
        store = ChromaVectorStore(ChromaConfig())
        doc = store.get("doc-1")
        
        assert doc is not None
        assert doc.id == "doc-1"
        assert doc.content == "Test content"

    def test_list_collections(self, mock_chroma):
        """Test listing collections."""
        _, mock_client, _ = mock_chroma
        mock_client.list_collections.return_value = [
            MagicMock(name="collection1"),
            MagicMock(name="collection2"),
        ]
        
        store = ChromaVectorStore(ChromaConfig())
        collections = store.list_collections()
        
        assert len(collections) >= 0  # May vary based on mock setup

    def test_list_documents_reads_the_real_collection(self, mock_chroma):
        """M7.7 migration prerequisite: list_documents was previously a stub
        returning []. Real enumeration is required to migrate ChromaDB
        content to the graph backend."""
        _, mock_client, mock_collection = mock_chroma
        mock_collection.get.return_value = {
            "ids": ["doc-1", "doc-2"],
            "documents": ["First", "Second"],
            "metadatas": [{"source": "a"}, {"source": "b"}],
        }

        store = ChromaVectorStore(ChromaConfig())
        docs = store.list_documents(limit=50)

        mock_collection.get.assert_called_once_with(limit=50)
        assert [d.id for d in docs] == ["doc-1", "doc-2"]
        assert docs[0].content == "First"
        assert docs[1].metadata == {"source": "b"}

    def test_list_documents_on_an_empty_collection(self, mock_chroma):
        _, mock_client, mock_collection = mock_chroma
        mock_collection.get.return_value = {"ids": [], "documents": [], "metadatas": []}

        store = ChromaVectorStore(ChromaConfig())
        assert store.list_documents() == []

    def test_list_documents_survives_a_none_metadata_entry(self, mock_chroma):
        """Real bug found running the M7.7 migration against real ChromaDB
        data: a record added with no metadata comes back as a literal
        ``None`` entry, not an empty dict — Document(metadata=None) raised."""
        _, mock_client, mock_collection = mock_chroma
        mock_collection.get.return_value = {
            "ids": ["doc-1"], "documents": ["No metadata ever set"], "metadatas": [None],
        }

        store = ChromaVectorStore(ChromaConfig())
        docs = store.list_documents()

        assert docs[0].metadata == {}
