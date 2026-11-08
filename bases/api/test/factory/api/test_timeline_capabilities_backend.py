"""Timeline capabilities must report the graph backend that is actually selected (#378)."""
from __future__ import annotations

import pytest

from factory.api.runtime import bridge


@pytest.mark.parametrize("legacy,real,expected", [
    ("networkx", "neo4j", "neo4j"),
    ("neo4j", None, "neo4j"),
    (None, None, "networkx"),
])
def test_graph_backend_prefers_the_selecting_key(monkeypatch, legacy, real, expected) -> None:
    monkeypatch.delenv("FACTORY_GRAPH_ADAPTER", raising=False)
    monkeypatch.delenv("GRAPH_BACKEND", raising=False)
    if legacy:
        monkeypatch.setenv("FACTORY_GRAPH_ADAPTER", legacy)
    if real:
        monkeypatch.setenv("GRAPH_BACKEND", real)
    reported = bridge._timeline_capabilities()
    assert expected in str(reported).lower()
