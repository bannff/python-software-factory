"""Tests for memory brick MCP contract compliance."""

from __future__ import annotations

import pytest

from factory.memory.interface import Runtime, create_server


class TestMCPContract:
    """Verify memory brick meets MCP contract requirements."""

    def test_create_server(self) -> None:
        """Test MCP server creation."""
        server = create_server()
        assert server is not None
        assert server.name == "memory-module"

    def test_interface_exports(self) -> None:
        """Test interface exports Runtime and create_server."""
        from factory.memory import interface

        assert hasattr(interface, "Runtime")
        assert hasattr(interface, "create_server")
        assert callable(interface.create_server)

    def test_runtime_has_health_check(self) -> None:
        """Test runtime exposes health_check method."""
        runtime = Runtime()
        health = runtime.health_check()

        assert health.healthy is True
        assert health.backend == "memory"

    def test_runtime_has_settings(self) -> None:
        """Test runtime exposes settings for config schema."""
        runtime = Runtime()
        settings = runtime.settings

        assert settings.service_name == "memory-module"
        assert settings.backend == "memory"


class TestRuntimeCapabilities:
    """Test runtime provides required capabilities."""

    def test_store_capability(self) -> None:
        """Test runtime can store memories."""
        runtime = Runtime()
        memory = runtime.store(
            user_id="test_user",
            content="Test memory content",
        )
        assert memory.id is not None
        assert memory.user_id == "test_user"

    def test_retrieve_capability(self) -> None:
        """Test runtime can retrieve memories."""
        runtime = Runtime()
        runtime.store(user_id="test_user", content="Important fact")

        results = runtime.retrieve(
            user_id="test_user",
            query="fact",
            min_relevance=0.1,
        )
        assert len(results) > 0

    def test_list_capability(self) -> None:
        """Test runtime can list memories."""
        runtime = Runtime()
        runtime.store(user_id="test_user", content="Memory 1")
        runtime.store(user_id="test_user", content="Memory 2")

        memories = runtime.list_all("test_user")
        assert len(memories) == 2

    def test_delete_capability(self) -> None:
        """Test runtime can delete memories."""
        runtime = Runtime()
        memory = runtime.store(user_id="test_user", content="To delete")

        assert runtime.delete(memory.id) is True
        assert runtime.get(memory.id) is None

    def test_consolidate_capability(self) -> None:
        """Test runtime can consolidate memories."""
        runtime = Runtime()
        runtime.store(user_id="test_user", content="Short term", memory_type="short_term")

        count = runtime.consolidate("test_user")
        assert count == 1

        memories = runtime.list_all("test_user")
        assert memories[0].memory_type == "long_term"

    def test_stats_capability(self) -> None:
        """Test runtime can provide statistics."""
        runtime = Runtime()
        runtime.store(user_id="test_user", content="Memory")

        stats = runtime.stats("test_user")
        assert stats.total_memories == 1
