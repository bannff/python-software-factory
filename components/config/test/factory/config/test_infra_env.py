"""Tests for InfraEnvConfigStore adapter.

Verifies the unprefixed env var convention: dot-notation keys map to
uppercase underscore env vars (neo4j.uri → NEO4J_URI).
"""

from __future__ import annotations

import os

import pytest

from factory.config.runtime.adapters.infra_env import InfraEnvConfigStore


class TestInfraEnvConfigStore:
    """Tests for InfraEnvConfigStore adapter."""

    @pytest.fixture
    def store(self) -> InfraEnvConfigStore:
        return InfraEnvConfigStore()

    @pytest.fixture(autouse=True)
    def cleanup(self) -> None:
        yield
        for k in ("NEO4J_URI", "NEO4J_USER", "STORAGE_DOC_BACKEND",
                   "SIMPLE", "MY_FLAG", "MY_PORT", "MY_BAD"):
            os.environ.pop(k, None)

    # --- Key mapping convention ---

    def test_key_mapping_single_segment(self, store: InfraEnvConfigStore) -> None:
        """Single-segment key uppercases without dots."""
        store.set("simple", "val")
        assert os.environ["SIMPLE"] == "val"

    def test_key_mapping_two_segments(self, store: InfraEnvConfigStore) -> None:
        """Two-segment key: neo4j.uri → NEO4J_URI."""
        store.set("neo4j.uri", "bolt://localhost:7687")
        assert os.environ["NEO4J_URI"] == "bolt://localhost:7687"

    def test_key_mapping_three_segments(self, store: InfraEnvConfigStore) -> None:
        """Three-segment key: storage.doc.backend → STORAGE_DOC_BACKEND."""
        store.set("storage.doc.backend", "s3")
        assert os.environ["STORAGE_DOC_BACKEND"] == "s3"

    # --- CRUD operations ---

    def test_get_set_roundtrip(self, store: InfraEnvConfigStore) -> None:
        store.set("neo4j.uri", "bolt://host:7687")
        assert store.get("neo4j.uri") == "bolt://host:7687"

    def test_get_missing_returns_none(self, store: InfraEnvConfigStore) -> None:
        assert store.get("nonexistent.key") is None

    def test_get_missing_returns_default(self, store: InfraEnvConfigStore) -> None:
        assert store.get("nonexistent.key", "fallback") == "fallback"

    def test_set_returns_true(self, store: InfraEnvConfigStore) -> None:
        assert store.set("simple", "v") is True

    def test_delete_existing(self, store: InfraEnvConfigStore) -> None:
        store.set("simple", "v")
        assert store.delete("simple") is True
        assert not store.exists("simple")

    def test_delete_missing(self, store: InfraEnvConfigStore) -> None:
        assert store.delete("nonexistent.key") is False

    def test_exists_true(self, store: InfraEnvConfigStore) -> None:
        store.set("neo4j.user", "neo4j")
        assert store.exists("neo4j.user")

    def test_exists_false(self, store: InfraEnvConfigStore) -> None:
        assert not store.exists("nonexistent.key")

    # --- get_typed ---

    def test_get_typed_int(self, store: InfraEnvConfigStore) -> None:
        store.set("my.port", "8080")
        assert store.get_typed("my.port", int) == 8080

    def test_get_typed_bool_truthy(self, store: InfraEnvConfigStore) -> None:
        for val in ("true", "1", "yes", "on"):
            store.set("my.flag", val)
            assert store.get_typed("my.flag", bool) is True

    def test_get_typed_bool_falsy(self, store: InfraEnvConfigStore) -> None:
        for val in ("false", "0", "no", "off"):
            store.set("my.flag", val)
            assert store.get_typed("my.flag", bool) is False

    def test_get_typed_missing_returns_default(self, store: InfraEnvConfigStore) -> None:
        assert store.get_typed("missing.key", int, 42) == 42

    def test_get_typed_bad_cast_returns_default(self, store: InfraEnvConfigStore) -> None:
        store.set("my.bad", "not_a_number")
        assert store.get_typed("my.bad", int, -1) == -1

    def test_get_typed_float(self, store: InfraEnvConfigStore) -> None:
        store.set("my.port", "3.14")
        assert store.get_typed("my.port", float) == pytest.approx(3.14)

    # --- keys / get_all ---

    def test_keys_with_prefix(self, store: InfraEnvConfigStore) -> None:
        store.set("neo4j.uri", "bolt://x")
        store.set("neo4j.user", "neo4j")
        store.set("storage.doc.backend", "s3")
        keys = store.keys("neo4j")
        assert "neo4j.uri" in keys
        assert "neo4j.user" in keys
        assert "storage.doc.backend" not in keys

    def test_get_all_with_prefix(self, store: InfraEnvConfigStore) -> None:
        store.set("neo4j.uri", "bolt://x")
        store.set("neo4j.user", "neo4j")
        result = store.get_all("neo4j")
        assert result["neo4j.uri"] == "bolt://x"
        assert result["neo4j.user"] == "neo4j"

    # --- health_check ---

    def test_health_check(self, store: InfraEnvConfigStore) -> None:
        health = store.health_check()
        assert health.healthy is True
        assert health.backend == "infra_env"
        assert health.latency_ms >= 0
        assert health.details == {"type": "unprefixed_env"}
