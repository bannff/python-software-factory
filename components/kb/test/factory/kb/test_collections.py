"""Tests for collection management."""


from factory.kb.runtime.collections import (
    CollectionConfig,
    CollectionRegistry,
    CollectionStats,
)


class TestCollectionConfig:
    """Tests for CollectionConfig model."""

    def test_create_config(self):
        """Test creating a collection config."""
        config = CollectionConfig(
            id="my-collection",
            name="My Collection",
            description="Test collection",
        )
        assert config.id == "my-collection"
        assert config.name == "My Collection"
        assert config.embedding_model == "default"

    def test_config_with_embedding_model(self):
        """Test config with custom embedding model."""
        config = CollectionConfig(
            id="custom",
            name="Custom",
            embedding_model="text-embedding-ada-002",
        )
        assert config.embedding_model == "text-embedding-ada-002"


class TestCollectionRegistry:
    """Tests for CollectionRegistry."""

    def test_register_collection(self):
        """Test registering a collection."""
        registry = CollectionRegistry()
        config = CollectionConfig(
            id="test",
            name="Test Collection",
        )
        registry.register(config)
        assert registry.get("test") == config

    def test_unregister_collection(self):
        """Test unregistering a collection."""
        registry = CollectionRegistry()
        config = CollectionConfig(id="test", name="Test")
        registry.register(config)
        registry.unregister("test")
        assert registry.get("test") is None

    def test_list_all_collections(self):
        """Test listing all collections."""
        registry = CollectionRegistry()
        config1 = CollectionConfig(id="c1", name="Collection 1")
        config2 = CollectionConfig(id="c2", name="Collection 2")
        registry.register(config1)
        registry.register(config2)
        
        all_configs = registry.list_all()
        assert len(all_configs) == 2


class TestCollectionStats:
    """Tests for CollectionStats model."""

    def test_create_stats(self):
        """Test creating collection stats."""
        stats = CollectionStats(
            collection_id="test",
            document_count=100,
            total_size_bytes=1024000,
        )
        assert stats.collection_id == "test"
        assert stats.document_count == 100
        assert stats.total_size_bytes == 1024000
