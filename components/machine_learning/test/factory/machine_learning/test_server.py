"""Behavior tests for typed ML tracking and learning read tools."""
from __future__ import annotations

import asyncio
from factory.machine_learning.server import create_mcp_server
from factory.machine_learning.runtime.runtime import reset_runtime
from factory.mcp_utils.registry import _services, set_service


def _tool(server, name): return asyncio.run(server.get_tool(name)).fn


def test_tracking_reads_preserve_domain_negative_results():
    reset_runtime()
    server = create_mcp_server()
    create = _tool(server, "tracking_create_experiment")
    created = create(name="test-exp", description="A test experiment")
    found = _tool(server, "tracking_get_experiment")(experiment_id=created.data.id)
    missing = _tool(server, "tracking_get_experiment")(experiment_id="missing")
    listed = _tool(server, "tracking_list_experiments")()
    assert found.ok and found.data.found and found.data.name == "test-exp"
    assert missing.ok and missing.data.found is False
    assert listed.ok and listed.data.count == 1


def test_learning_reads_project_event_chain():
    original = _services.get("tool_invoker")
    events = {"graph.launched": [], "graph.completed": [{"id": "done", "type": "graph.completed", "source": "test", "timestamp": "2026-01-01", "payload": {"run_id": "run-1", "workflow_run_id": "wf-1", "status": "completed"}}], "graph.failed": [], "reward.computed": [], "wallet.rewarded": [], "memory.learning_stored": [], "convergence.checked": []}
    def invoker(name, **kwargs):
        assert name == "events_query_events"
        return {
            "schema_version": "v1", "ok": True,
            "data": {"events": events.get(kwargs.get("event_type"), [])},
            "error": None, "idempotency_key": None,
        }
    set_service("tool_invoker", invoker)
    try:
        server = create_mcp_server()
        listed = _tool(server, "ml_list_learning_runs")()
        run = _tool(server, "ml_get_learning_run")(run_id="run-1")
        missing = _tool(server, "ml_get_learning_run")(run_id="missing")
        assert listed.ok and listed.data.count == 1
        assert run.ok and run.data.found and run.data.run["run_id"] == "run-1"
        assert missing.ok and missing.data.found is False
    finally:
        if original is None: _services.pop("tool_invoker", None)
        else: set_service("tool_invoker", original)
