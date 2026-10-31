"""Real Telemetry exporter → MCP aggregator → Graph callback integration."""
from __future__ import annotations

import shutil
import sqlite3
import threading
from pathlib import Path
from queue import Queue

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from factory.graph.runtime.runtime import GraphRuntime
from factory.graph.server import create_mcp_server as create_graph_server
from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.interface import get_service, set_service
from factory.telemetry.runtime.runtime import TelemetryRuntime
from factory.telemetry.server import create_mcp_server as create_telemetry_server

ROOT = Path(__file__).resolve().parents[5]


def _flush_with_timeout(runtime: TelemetryRuntime) -> dict:
    results: Queue[dict] = Queue(maxsize=1)
    worker = threading.Thread(
        target=lambda: results.put(runtime.flush_telemetry(timeout_ms=2_000)),
        daemon=True,
    )
    worker.start()
    worker.join(timeout=5)
    assert not worker.is_alive(), "force_flush deadlocked in exporter callback"
    return results.get_nowait()


def test_span_flush_materializes_through_real_graph_callback(
    tmp_path: Path, monkeypatch,
) -> None:
    config = tmp_path / "telemetry"
    shutil.copytree(ROOT / "projects/companion_x/telemetry", config)
    graph_server = create_graph_server(
        GraphRuntime({"default_backend": "networkx"})
    )
    aggregator = MCPAggregator(ToolCatalog("telemetry-graph-integration"))
    aggregator.set_available_bricks(["telemetry", "graph"])
    aggregator._lazy._cache["graph"] = graph_server
    invoker = NativeEnvelopeInvoker(aggregator)
    service_names = (
        "brick_tools", "tool_invoker", "tool_invoker_envelope",
        "provenance_target_resolver",
    )
    previous = {name: get_service(name) for name in service_names}
    events: list[dict] = []
    monkeypatch.setattr(
        "factory.mcp_server.runtime.instrumentation.event_bus.publish",
        lambda event: events.append(event),
    )
    set_service("brick_tools", aggregator.get_brick_tools)
    set_service("tool_invoker", aggregator.invoke_tool)
    set_service("tool_invoker_envelope", invoker)
    # The immutable target contract is v1; callback dispatch remains the real
    # aggregator/Graph path under test.
    set_service("provenance_target_resolver", lambda target: target.version)
    try:
        runtime = TelemetryRuntime(config)
        runtime.initialize()
        aggregator._lazy._cache["telemetry"] = create_telemetry_server(runtime)
        assert runtime.health_check()["ok"] is True

        tracer = runtime.otel.tracer_provider.get_tracer("integration")
        with tracer.start_as_current_span("managed-run", attributes={
            "run_id": "wfr:v1:live-probe",
            "workflow_run_id": "wfr:v1:live-probe",
            "graph_id": "probe-graph",
            "agent_id": "probe-agent",
        }):
            pass

        flush = _flush_with_timeout(runtime)
        assert flush["ok"] is True, flush
        with sqlite3.connect(config / "provenance.sqlite3") as connection:
            rows = connection.execute(
                "SELECT materialized FROM records"
            ).fetchall()
        assert rows and all(row[0] == 1 for row in rows)
        assert any(
            event.get("brick") == "graph"
            and event.get("tool") == "graph_write_relationship"
            and event.get("success") is True
            for event in events
        )
    finally:
        for name, value in previous.items():
            set_service(name, value)