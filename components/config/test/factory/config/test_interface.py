"""Tests for config brick interface convenience functions.

Verifies get_infra() and get_neo4j_config() delegate correctly
to the layered config runtime.
"""

from __future__ import annotations

import os

import pytest

from factory.config.runtime.runtime import reset_runtime


class TestGetInfra:
    """Tests for get_infra() convenience function."""

    @pytest.fixture(autouse=True)
    def reset(self) -> None:
        reset_runtime()
        yield
        for k in ("NEO4J_URI", "MEMORY_BACKEND", "GRAPH_BACKEND"):
            os.environ.pop(k, None)
        reset_runtime()

    def test_get_infra_reads_env(self) -> None:
        """get_infra resolves keys from environment variables."""
        from factory.config.interface import get_infra

        os.environ["MEMORY_BACKEND"] = "redis"
        assert get_infra("memory.backend") == "redis"

    def test_get_infra_returns_default(self) -> None:
        """get_infra returns default when key is absent."""
        from factory.config.interface import get_infra

        assert get_infra("missing.key", "fallback") == "fallback"

    def test_get_infra_default_none(self) -> None:
        """get_infra returns None when no default specified."""
        from factory.config.interface import get_infra

        assert get_infra("missing.key") is None

    def test_get_infra_env_overrides_default(self) -> None:
        """Env var takes precedence over the provided default."""
        from factory.config.interface import get_infra

        os.environ["GRAPH_BACKEND"] = "neo4j"
        assert get_infra("graph.backend", "memory") == "neo4j"


class TestGetNeo4jConfig:
    """Tests for get_neo4j_config() convenience function."""

    @pytest.fixture(autouse=True)
    def reset(self) -> None:
        reset_runtime()
        yield
        for k in ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD", "NEO4J_DATABASE"):
            os.environ.pop(k, None)
        reset_runtime()

    def test_defaults(self) -> None:
        """Returns sensible defaults when no env vars set."""
        from factory.config.interface import get_neo4j_config

        cfg = get_neo4j_config()
        assert cfg == {
            "uri": "bolt://localhost:7687",
            "user": "neo4j",
            "password": "password",
            "database": "neo4j",
        }

    def test_env_overrides(self) -> None:
        """Env vars override all defaults."""
        from factory.config.interface import get_neo4j_config

        os.environ["NEO4J_URI"] = "bolt://prod:7687"
        os.environ["NEO4J_USER"] = "admin"
        os.environ["NEO4J_PASSWORD"] = "s3cret"
        os.environ["NEO4J_DATABASE"] = "mydb"

        cfg = get_neo4j_config()
        assert cfg["uri"] == "bolt://prod:7687"
        assert cfg["user"] == "admin"
        assert cfg["password"] == "s3cret"
        assert cfg["database"] == "mydb"

    def test_partial_override(self) -> None:
        """Only overridden keys change; others keep defaults."""
        from factory.config.interface import get_neo4j_config

        os.environ["NEO4J_URI"] = "bolt://custom:7687"

        cfg = get_neo4j_config()
        assert cfg["uri"] == "bolt://custom:7687"
        assert cfg["user"] == "neo4j"  # default
        assert cfg["password"] == "password"  # default

    def test_returns_dict_with_four_keys(self) -> None:
        """Return value always has exactly uri, user, password, database."""
        from factory.config.interface import get_neo4j_config

        cfg = get_neo4j_config()
        assert set(cfg.keys()) == {"uri", "user", "password", "database"}
