"""graph_sink must read the shared graph-sink gate.

The writer and the poller have to agree on one flag; if the writer drifted to
its own env parsing, the poller could skip while writes still happen (or the
reverse).
"""
from __future__ import annotations

import pytest

from factory.mcp_server.runtime import graph_sink
from factory.mcp_utils.graph_sink_gate import GRAPH_SINK_ENV, graph_sink_enabled


@pytest.mark.parametrize("value", ["1", "true", "yes", "0", "false", "no", ""])
def test_is_enabled_mirrors_the_shared_gate(monkeypatch, value: str) -> None:
    monkeypatch.setenv(GRAPH_SINK_ENV, value)
    assert graph_sink._is_enabled() is graph_sink_enabled()


def test_is_enabled_defaults_off(monkeypatch) -> None:
    monkeypatch.delenv(GRAPH_SINK_ENV, raising=False)
    assert graph_sink._is_enabled() is False
