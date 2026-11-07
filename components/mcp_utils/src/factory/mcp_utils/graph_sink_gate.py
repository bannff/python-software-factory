"""Single gate for the graph telemetry sink.

The writer (``factory.mcp_server.runtime.graph_sink``) and the reader
(``tool_event_stream`` polling ``ToolInvocation`` entities) must read the same
flag. When the sink is off nothing is ever written, so a poller would scan an
absent label forever and the graph driver would log a warning per scan.
"""
from __future__ import annotations

import os

GRAPH_SINK_ENV = "TELEMETRY_GRAPH_SINK"
_TRUTHY = frozenset({"1", "true", "yes"})


def graph_sink_enabled() -> bool:
    """True when tool invocations are materialised into the graph."""
    return os.environ.get(GRAPH_SINK_ENV, "false").strip().lower() in _TRUTHY


__all__ = ["GRAPH_SINK_ENV", "graph_sink_enabled"]
