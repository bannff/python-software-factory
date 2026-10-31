"""Graph and probe setup shared by the managed-lineage integration harness."""
from __future__ import annotations

import asyncio
import threading
from typing import Any

from pydantic import BaseModel, ConfigDict

from factory.mcp_utils.interface import ToolResult, get_envelope, ok, operational
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog


class _ProbeInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    label: str


class _ProbeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    label: str


class ImmediateQueue:
    def put(self, callback: Any) -> None:
        callback()


def create_probe_server(
    observed: dict[str, dict[str, Any]], lock: threading.Lock,
) -> ToolCatalog:
    """Build a probe that records the envelope propagated to each graph node."""
    server = ToolCatalog("lineage-probe")

    @server.tool(name="probe_record")
    @operational(input_model=_ProbeInput, output_model=_ProbeOutput)
    async def record(label: str) -> ToolResult[_ProbeOutput]:
        await asyncio.sleep(0.02 if label == "a" else 0.01)
        with lock:
            observed[label] = dict(get_envelope() or {})
        return ok(_ProbeOutput(label=label))

    return server


def install_graph_sink(graph_server: ToolCatalog, monkeypatch: Any) -> None:
    """Route telemetry sink writes synchronously into the harness graph server."""
    from factory.mcp_server.runtime import graph_sink

    names = (
        "graph_add_entity", "graph_add_relationship",
        "graph_get_tool_invocations_for_run",
    )
    monkeypatch.setattr(graph_sink, "_graph_runtime", {
        name: asyncio.run(graph_server.get_tool(name)) for name in names
    })
    for name, value in (
        ("_invocation_counter", {}), ("_last_invocation_by_session", {}),
        ("_run_invocation_counter", {}), ("_last_invocation_by_run", {}),
        ("_current_workflow_run_id", None),
    ):
        monkeypatch.setattr(graph_sink, name, value)
    monkeypatch.setenv("TELEMETRY_GRAPH_SINK", "true")
    monkeypatch.setattr(graph_sink, "_ensure_drain_thread", lambda: None)
    monkeypatch.setattr(graph_sink, "_SINK_QUEUE", ImmediateQueue())
