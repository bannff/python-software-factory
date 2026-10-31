"""Tests for the process-level service registry.

Verifies set_service/get_service key-value semantics: store, retrieve,
missing key returns None, and overwrite replaces the value.
"""

from __future__ import annotations

from factory.mcp_utils.registry import set_service, get_service, _services


class TestServiceRegistry:
    """Unit tests for set_service / get_service."""

    def setup_method(self) -> None:
        """Clear registry before each test for isolation."""
        _services.clear()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        _services.clear()

    def test_set_and_get(self) -> None:
        """Stored value is retrievable."""
        set_service("invoker", "my_callback")
        assert get_service("invoker") == "my_callback"

    def test_get_missing_returns_none(self) -> None:
        """Missing key returns None, not KeyError."""
        assert get_service("nonexistent") is None

    def test_overwrite_replaces_value(self) -> None:
        """Setting the same key twice keeps the latest value."""
        set_service("invoker", "v1")
        set_service("invoker", "v2")
        assert get_service("invoker") == "v2"

    def test_multiple_keys_independent(self) -> None:
        """Different keys store independent values."""
        set_service("a", 1)
        set_service("b", 2)
        assert get_service("a") == 1
        assert get_service("b") == 2

    def test_stores_callable(self) -> None:
        """Registry can store and retrieve callables."""
        fn = lambda x: x + 1  # noqa: E731
        set_service("adder", fn)
        retrieved = get_service("adder")
        assert retrieved(5) == 6

    def test_stores_none_value(self) -> None:
        """Storing None as a value is distinct from missing key."""
        set_service("nullable", None)
        # The key exists but value is None — same return as missing.
        # This is a known semantic: get_service can't distinguish
        # "key exists with None" from "key missing".
        assert get_service("nullable") is None
