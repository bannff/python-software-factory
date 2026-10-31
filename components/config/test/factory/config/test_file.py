"""Tests for file-based config adapter."""

import pytest
from pathlib import Path

from factory.config.runtime.adapters.file_adapter import FileConfigStore


class TestFileConfigStore:
    """Tests for FileConfigStore adapter."""

    @pytest.fixture
    def config(self, tmp_path: Path) -> FileConfigStore:
        """Create a file config store."""
        return FileConfigStore(path=str(tmp_path / "config.yaml"))

    def test_get_set(self, config: FileConfigStore) -> None:
        """Test basic get/set."""
        config.set("key1", "value1")
        assert config.get("key1") == "value1"

    def test_get_missing(self, config: FileConfigStore) -> None:
        """Test getting a missing key."""
        assert config.get("missing") is None
        assert config.get("missing", "default") == "default"

    def test_nested_keys(self, config: FileConfigStore) -> None:
        """Test nested key access with dot notation."""
        config.set("database.host", "localhost")
        config.set("database.port", 5432)

        assert config.get("database.host") == "localhost"
        assert config.get("database.port") == 5432

    def test_get_typed(self, config: FileConfigStore) -> None:
        """Test getting typed values."""
        config.set("count", 42)
        assert config.get_typed("count", int) == 42

        config.set("ratio", "3.14")
        assert config.get_typed("ratio", float) == 3.14

    def test_delete(self, config: FileConfigStore) -> None:
        """Test deleting a key."""
        config.set("to_delete", "value")
        assert config.exists("to_delete")

        assert config.delete("to_delete")
        assert not config.exists("to_delete")

    def test_delete_nested(self, config: FileConfigStore) -> None:
        """Test deleting a nested key."""
        config.set("app.name", "test")
        config.set("app.version", "1.0")

        assert config.delete("app.name")
        assert not config.exists("app.name")
        assert config.exists("app.version")

    def test_exists(self, config: FileConfigStore) -> None:
        """Test checking existence."""
        assert not config.exists("key")
        config.set("key", "value")
        assert config.exists("key")

    def test_keys(self, config: FileConfigStore) -> None:
        """Test listing keys."""
        config.set("app.name", "test")
        config.set("app.version", "1.0")
        config.set("db.host", "localhost")

        all_keys = config.keys()
        assert len(all_keys) == 3

        app_keys = config.keys("app")
        assert len(app_keys) == 2

    def test_get_all(self, config: FileConfigStore) -> None:
        """Test getting all values."""
        config.set("a", "1")
        config.set("b", "2")

        all_values = config.get_all()
        assert len(all_values) == 2

    def test_persistence(self, tmp_path: Path) -> None:
        """Test that config persists to file."""
        path = str(tmp_path / "persist.yaml")

        config1 = FileConfigStore(path=path)
        config1.set("persistent", "value")

        # Create new instance pointing to same file
        config2 = FileConfigStore(path=path)
        assert config2.get("persistent") == "value"

    def test_health_check(self, config: FileConfigStore) -> None:
        """Test health check."""
        health = config.health_check()
        assert health.healthy
        assert health.backend == "file"

    def test_json_file(self, tmp_path: Path) -> None:
        """Test JSON file support."""
        config = FileConfigStore(path=str(tmp_path / "config.json"))
        config.set("key", "value")
        assert config.get("key") == "value"
