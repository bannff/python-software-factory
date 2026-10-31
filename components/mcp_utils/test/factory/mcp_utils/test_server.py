"""Tests for make_lazy_runner shared utility.

This is infrastructure used by every brick — verify the contract:
1. Factory is called lazily (not at import time)
2. Singleton: repeated calls return the same instance
3. main() delegates to .run() on the singleton
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

from factory.mcp_utils.server import make_lazy_runner


def _make_fake_factory():
    """Return a mock factory that produces distinguishable servers."""
    server = MagicMock(name="fake-mcp-server")
    factory = MagicMock(return_value=server)
    return factory, server


class TestMakeLazyRunner:
    """Tests for make_lazy_runner."""

    def test_returns_two_callables(self) -> None:
        factory, _ = _make_fake_factory()
        get, main = make_lazy_runner(factory)
        assert callable(get)
        assert callable(main)

    def test_factory_not_called_at_creation(self) -> None:
        factory, _ = _make_fake_factory()
        make_lazy_runner(factory)
        factory.assert_not_called()

    def test_factory_called_on_first_get(self) -> None:
        factory, server = _make_fake_factory()
        get, _ = make_lazy_runner(factory)
        result = get()
        factory.assert_called_once()
        assert result is server

    def test_singleton_returns_same_instance(self) -> None:
        factory, server = _make_fake_factory()
        get, _ = make_lazy_runner(factory)
        first = get()
        second = get()
        third = get()
        factory.assert_called_once()
        assert first is second is third is server

    def test_main_calls_run_on_singleton(self) -> None:
        factory, server = _make_fake_factory()
        _, main = make_lazy_runner(factory)
        main()
        factory.assert_called_once()
        server.run.assert_called_once()

    def test_separate_runners_are_independent(self) -> None:
        factory_a, server_a = _make_fake_factory()
        factory_b, server_b = _make_fake_factory()
        get_a, _ = make_lazy_runner(factory_a)
        get_b, _ = make_lazy_runner(factory_b)
        assert get_a() is server_a
        assert get_b() is server_b
        assert get_a() is not get_b()
