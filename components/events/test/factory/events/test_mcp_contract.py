"""Events MCP contract and native resource regressions."""
from __future__ import annotations

import asyncio
import json

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.events.runtime.runtime import EventsRuntime
from factory.events.server import create_mcp_server
from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.interface import reset_envelope, set_envelope


def _tool(mcp, name: str):
    return asyncio.run(mcp.get_tool(name)).fn


def test_contract_tools_return_enveloped_data(tmp_path) -> None:
    mcp = create_mcp_server(EventsRuntime(tmp_path))
    capabilities = _tool(mcp, "events_get_capabilities")()
    health = _tool(mcp, "events_health_check")()
    schema = _tool(mcp, "events_describe_config_schema")()
    assert capabilities.ok and capabilities.data.features["event_publishing"]
    assert health.ok and health.data.status in {"healthy", "unhealthy"}
    assert schema.ok and "reward.computed" in schema.data.learning_event_schemas


def test_history_tools_and_resource_preserve_payloads(tmp_path) -> None:
    mcp = create_mcp_server(EventsRuntime(tmp_path))
    published = _tool(mcp, "events_publish")(event_type="provenance.received",
        payload={"run_id": "run-123", "score": 0.75}, source="events.rewards",
        tenant_id="tenant-1", principal_id="user-1", request_id="req-1")
    assert published.ok
    history = _tool(mcp, "events_query_history")(event_type="provenance.received",
        payload_key="run_id", payload_value="run-123")
    assert history.ok and history.data.total >= 1
    entry = next(item for item in history.data.entries if item.event_id == published.data.event_id)
    assert entry.payload["run_id"] == "run-123" and entry.principal_id == "user-1"
    resource = asyncio.run(mcp.read_resource(f"events://history/{published.data.event_id}"))
    assert json.loads(resource.contents[0].content)["payload"]["score"] == 0.75


def test_publish_and_replay_use_trusted_ambient_correlation(tmp_path) -> None:
    runtime = EventsRuntime(tmp_path)
    mcp = create_mcp_server(runtime)
    publish = _tool(mcp, "events_publish")
    replay = _tool(mcp, "events_replay")
    token = set_envelope({
        "tenant_id": "trusted-tenant", "principal_id": "trusted-principal",
        "run_id": "trusted-run",
        "attributes": {"collision": "trusted", "ambient_only": "yes"},
    })
    try:
        published = publish(
            event_type="provenance.received",
            payload={"correlation_id": "attacker", "value": 1},
            source="tests",
            tenant_id="attacker-tenant", principal_id="attacker-principal",
            request_id="attacker-request",
            attributes={"collision": "attacker", "caller_only": "yes"},
        )
        assert published.ok
        entry = next(item for item in runtime.list_event_history()
                     if item.event_id == published.data.event_id)
        assert entry.tenant_id == "trusted-tenant"
        assert entry.principal_id == "trusted-principal"
        assert entry.correlation_id == "trusted-run"
        assert entry.metadata["collision"] == "trusted"
        assert entry.metadata["caller_only"] == "yes"
        assert entry.metadata["ambient_only"] == "yes"
        assert entry.payload["correlation_id"] == "trusted-run"

        replayed = replay(
            event_id=published.data.event_id, request_id="attacker-replay",
            attributes={"replay_only": "yes"},
        )
        assert replayed.ok
        replay_entry = next(item for item in runtime.list_event_history()
                            if item.event_id == replayed.data.new_event_id)
        assert replay_entry.correlation_id == "trusted-run"
        assert replay_entry.metadata["collision"] == "trusted"
        assert replay_entry.metadata["replay_only"] == "yes"
    finally:
        reset_envelope(token)


def test_native_invoker_to_events_preserves_trusted_ambient_context(tmp_path) -> None:
    runtime = EventsRuntime(tmp_path)
    events = create_mcp_server(runtime)
    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["events"])
    aggregator._lazy._cache["events"] = events
    token = set_envelope({
        "tenant_id": "trusted-tenant", "run_id": "trusted-run",
        "attributes": {"collision": "trusted"},
    })
    try:
        result = NativeEnvelopeInvoker(aggregator)(
            {"brick_name": "events", "tool_name": "events_publish"},
            arguments={
                "event_type": "provenance.received",
                "payload": {"correlation_id": "attacker"},
                "source": "tests",
                "tenant_id": "attacker-tenant",
                "request_id": "attacker-request",
                "attributes": {"collision": "attacker", "caller_only": "yes"},
            },
            idempotency_key="attempt-1",
            envelope={"tenant_id": "attacker-tenant", "request_id": "attacker-request"},
        )
    finally:
        reset_envelope(token)

    assert result["ok"] is True
    entry = runtime.list_event_history()[0]
    assert entry.tenant_id == "trusted-tenant"
    assert entry.correlation_id == "trusted-run"
    assert entry.metadata["collision"] == "trusted"
    assert entry.metadata["workflow_attempt_id"] == "attempt-1"
    assert entry.payload["correlation_id"] == "trusted-run"


def test_dashboard_tools_are_registered_and_enveloped(tmp_path) -> None:
    mcp = create_mcp_server(EventsRuntime(tmp_path))
    _tool(mcp, "events_publish")(event_type="workflow.run_started",
        payload={"run_id": "run-123"}, source="workflow")
    summary = _tool(mcp, "events_get_dashboard_summary")()
    views = _tool(mcp, "events_get_views")()
    event_id = summary.data.events[0]["event_id"]
    history = _tool(mcp, "events_get_event_history_entry")(event_id=event_id)
    assert summary.ok and summary.data.overview["events"] >= 1
    assert views.ok and views.data.views[0]["id"] == "events-stream"
    assert history.ok and history.data.found and history.data.entry.payload["run_id"] == "run-123"
