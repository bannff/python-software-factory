"""Tests for memory runtime core functionality."""

from __future__ import annotations

import pytest

from factory.memory.runtime.adapters.memory import InMemoryStore
from factory.memory.runtime.models import MemoryQuery, Settings
from factory.memory.runtime.runtime import MemoryRuntime


class TestInMemoryStore:
    """Tests for in-memory adapter."""

    def test_store_and_get(self) -> None:
        """Test storing and retrieving a memory."""
        store = InMemoryStore()
        memory = store.store(
            user_id="user1",
            content="User likes dark mode",
            memory_type="long_term",
            category="preference",
        )

        assert memory.id is not None
        assert memory.user_id == "user1"
        assert memory.content == "User likes dark mode"
        assert memory.memory_type == "long_term"

        retrieved = store.get(memory.id)
        assert retrieved is not None
        assert retrieved.id == memory.id

    def test_retrieve_with_relevance(self) -> None:
        """Test semantic retrieval with relevance scoring."""
        store = InMemoryStore()
        store.store("user1", "User prefers dark mode for UI", category="preference")
        store.store("user1", "User lives in Seattle", category="fact")
        store.store("user1", "User likes Python programming", category="fact")

        query = MemoryQuery(
            user_id="user1",
            query="What UI preferences does the user have?",
            min_relevance=0.1,
            limit=5,
        )
        results = store.retrieve(query)

        assert len(results) > 0
        # Dark mode should be most relevant to UI preferences
        assert "dark mode" in results[0].content.lower()

    def test_list_all(self) -> None:
        """Test listing all memories for a user."""
        store = InMemoryStore()
        store.store("user1", "Memory 1")
        store.store("user1", "Memory 2")
        store.store("user2", "Other user memory")

        user1_memories = store.list_all("user1")
        assert len(user1_memories) == 2

        user2_memories = store.list_all("user2")
        assert len(user2_memories) == 1

    def test_delete(self) -> None:
        """Test deleting a memory."""
        store = InMemoryStore()
        memory = store.store("user1", "To be deleted")

        assert store.delete(memory.id) is True
        assert store.get(memory.id) is None
        assert store.delete(memory.id) is False  # Already deleted

    def test_update(self) -> None:
        """Test correcting a memory's content in place (row 43)."""
        store = InMemoryStore()
        memory = store.store("user1", "original content")

        updated = store.update(memory.id, "corrected content")
        assert updated is not None
        assert updated.content == "corrected content"
        assert updated.updated_at is not None
        assert store.get(memory.id).content == "corrected content"

    def test_update_unknown_memory_returns_none(self) -> None:
        """Test correcting a memory that does not exist."""
        store = InMemoryStore()
        assert store.update("nonexistent-id", "new content") is None

    def test_delete_user_memories(self) -> None:
        """Test deleting all memories for a user."""
        store = InMemoryStore()
        store.store("user1", "Memory 1")
        store.store("user1", "Memory 2")
        store.store("user2", "Other user")

        count = store.delete_user_memories("user1")
        assert count == 2
        assert len(store.list_all("user1")) == 0
        assert len(store.list_all("user2")) == 1

    def test_consolidate(self) -> None:
        """Test consolidating short-term to long-term."""
        store = InMemoryStore()
        store.store("user1", "Short term 1", memory_type="short_term")
        store.store("user1", "Short term 2", memory_type="short_term")
        store.store("user1", "Already long term", memory_type="long_term")

        count = store.consolidate("user1")
        assert count == 2

        memories = store.list_all("user1")
        for m in memories:
            assert m.memory_type == "long_term"

    def test_stats(self) -> None:
        """Test getting statistics."""
        store = InMemoryStore()
        store.store("user1", "Preference", category="preference")
        store.store("user1", "Fact", category="fact")
        store.store("user2", "Other", category="custom")

        all_stats = store.stats()
        assert all_stats.total_memories == 3

        user1_stats = store.stats("user1")
        assert user1_stats.total_memories == 2

    def test_health_check(self) -> None:
        """Test health check."""
        store = InMemoryStore()
        health = store.health_check()

        assert health.healthy is True
        assert health.backend == "memory"


class TestMemoryRuntime:
    """Tests for memory runtime."""

    def test_default_initialization(self) -> None:
        """Test runtime initializes with defaults."""
        runtime = MemoryRuntime()
        assert runtime.settings.backend == "memory"

    def test_store_and_retrieve(self) -> None:
        """Test runtime store and retrieve flow."""
        runtime = MemoryRuntime()

        memory = runtime.store(
            user_id="agent1",
            content="The user mentioned they work at Acme Corp",
            category="fact",
        )
        assert memory.id is not None

        results = runtime.retrieve(
            user_id="agent1",
            query="Where does the user work?",
            min_relevance=0.1,
        )
        assert len(results) > 0
        assert "Acme" in results[0].content

    def test_custom_settings(self) -> None:
        """Test runtime with custom settings."""
        settings = Settings(
            service_name="custom-memory",
            default_ttl_seconds=3600,
            max_memories_per_user=500,
        )
        runtime = MemoryRuntime(settings=settings)

        assert runtime.settings.default_ttl_seconds == 3600
        assert runtime.settings.max_memories_per_user == 500
