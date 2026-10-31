"""Tests for PydanticSettingsStore adapter (pydantic-settings library).

Exercises real pydantic-settings env loading — no mocks.
"""

from __future__ import annotations

import os

import pytest

from factory.config.runtime.adapters.pydantic_adapter import PydanticSettingsStore


@pytest.fixture
def store() -> PydanticSettingsStore:
    return PydanticSettingsStore(prefix="TEST_CFG_")


@pytest.fixture(autouse=True)
def clean_env():
    """Remove test env vars after each test."""
    yield
    for k in list(os.environ):
        if k.startswith("TEST_CFG_"):
            del os.environ[k]


class TestPydanticSettingsStore:
    """Tests for PydanticSettingsStore using real pydantic-settings."""

    def test_import(self) -> None:
        """PydanticSettingsStore and pydantic_settings are importable."""
        from pydantic_settings import BaseSettings
        assert BaseSettings is not None
        assert PydanticSettingsStore is not None

    def test_instantiation(self) -> None:
        """Can create a store with custom prefix."""
        store = PydanticSettingsStore(prefix="MY_APP_")
        assert store is not None

    def test_get_missing_returns_default(self, store: PydanticSettingsStore) -> None:
        """get() returns default for missing keys."""
        assert store.get("nonexistent") is None
        assert store.get("nonexistent", "fallback") == "fallback"

    def test_set_and_get(self, store: PydanticSettingsStore) -> None:
        """set() writes to env, get() reads it back."""
        store.set("db.host", "localhost")
        assert store.get("db.host") == "localhost"

    def test_exists(self, store: PydanticSettingsStore) -> None:
        """exists() checks env var presence."""
        assert store.exists("db.port") is False
        store.set("db.port", "5432")
        assert store.exists("db.port") is True

    def test_delete(self, store: PydanticSettingsStore) -> None:
        """delete() removes the env var."""
        store.set("temp.key", "value")
        assert store.delete("temp.key") is True
        assert store.exists("temp.key") is False
        assert store.delete("temp.key") is False  # already gone

    def test_keys(self, store: PydanticSettingsStore) -> None:
        """keys() lists keys with the configured prefix."""
        store.set("alpha", "1")
        store.set("beta", "2")
        k = store.keys()
        assert "alpha" in k
        assert "beta" in k

    def test_get_all(self, store: PydanticSettingsStore) -> None:
        """get_all() returns all key-value pairs."""
        store.set("x", "10")
        store.set("y", "20")
        all_vals = store.get_all()
        assert all_vals["x"] == "10"
        assert all_vals["y"] == "20"

    def test_get_typed_int(self, store: PydanticSettingsStore) -> None:
        """get_typed() coerces to int."""
        store.set("port", "8080")
        assert store.get_typed("port", int) == 8080

    def test_get_typed_bool(self, store: PydanticSettingsStore) -> None:
        """get_typed() coerces to bool."""
        store.set("debug", "true")
        assert store.get_typed("debug", bool) is True
        store.set("debug", "false")
        assert store.get_typed("debug", bool) is False

    def test_health_check(self, store: PydanticSettingsStore) -> None:
        """health_check reports healthy."""
        health = store.health_check()
        assert health.healthy is True
        assert health.backend == "pydantic-settings"
