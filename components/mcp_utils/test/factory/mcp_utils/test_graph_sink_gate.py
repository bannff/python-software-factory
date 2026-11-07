"""Gate semantics for ``TELEMETRY_GRAPH_SINK``.

The gate is shared by the writer (graph_sink) and the reader (tool poller), so
its parsing must be stable: truthy spellings enable, everything else disables,
and the default is off.
"""
from __future__ import annotations

import pytest

from factory.mcp_utils.graph_sink_gate import GRAPH_SINK_ENV, graph_sink_enabled


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", " True ", "YES"])
def test_truthy_spellings_enable_the_sink(monkeypatch, value: str) -> None:
    monkeypatch.setenv(GRAPH_SINK_ENV, value)
    assert graph_sink_enabled() is True


@pytest.mark.parametrize("value", ["0", "false", "no", "", "off", "2"])
def test_other_spellings_disable_the_sink(monkeypatch, value: str) -> None:
    monkeypatch.setenv(GRAPH_SINK_ENV, value)
    assert graph_sink_enabled() is False


def test_absent_flag_disables_the_sink(monkeypatch) -> None:
    monkeypatch.delenv(GRAPH_SINK_ENV, raising=False)
    assert graph_sink_enabled() is False
