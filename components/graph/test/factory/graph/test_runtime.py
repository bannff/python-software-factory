"""Tests for graph runtime - Core tests.

See also:
- test_runtime_networkx.py - NetworkX adapter tests
"""

import pytest

from factory.graph.runtime.runtime import (
    GraphRuntime,
    get_runtime,
    reset_runtime,
)


class TestGraphRuntime:
    """Tests for GraphRuntime factory."""

    def setup_method(self) -> None:
        reset_runtime()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_available_backends(self) -> None:
        """Should list available backends."""
        backends = GraphRuntime.available_backends()
        assert "networkx" in backends
        assert "neo4j" in backends

    def test_get_runtime_singleton(self) -> None:
        """Should return same runtime instance."""
        r1 = get_runtime()
        r2 = get_runtime()
        assert r1 is r2

    def test_reset_runtime(self) -> None:
        """Should reset runtime instance."""
        r1 = get_runtime()
        reset_runtime()
        r2 = get_runtime()
        assert r1 is not r2

    def test_unknown_backend_raises(self) -> None:
        """Should raise for unknown backend."""
        runtime = GraphRuntime()
        with pytest.raises(ValueError, match="Unknown graph backend"):
            runtime.get_graph("unknown")

    def test_get_graph_networkx(self) -> None:
        """Should create NetworkX graph."""
        runtime = GraphRuntime()
        graph = runtime.get_graph("networkx")
        assert graph is not None

    def test_health_check_empty(self) -> None:
        """Should return empty health when no graphs active."""
        runtime = GraphRuntime()
        health = runtime.health_check()
        assert health == {}
