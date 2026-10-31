"""Protected Events-to-Graph relationship projection integration."""
from __future__ import annotations

import asyncio
import hashlib
import time

import pytest

from factory.events.runtime.runtime import EventsRuntime
from factory.events.server import create_mcp_server as create_events_server
from factory.graph.runtime.neighborhood import encode_node_id
from factory.graph.runtime.runtime import GraphRuntime
from factory.graph.server import create_mcp_server as create_graph_server
from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.interface import (
    ServiceOnlyAccessError, get_service, protected_canonical_json, set_service,
)


def _record() -> dict:
    return {
        "source_system": "lessons", "action": "upsert",
        "subject_kind": "lesson", "subject_local_id": "lesson-1",
        "subject_type": "Lesson", "source_digest": "a" * 64,
        "references": [{
            "kind": "workflow-run", "local_id": "run-1",
            "entity_type": "WorkflowRun", "relation_type": "learned_in",
        }],
    }


@pytest.mark.asyncio
async def test_public_projection_event_is_refused_before_dispatch(tmp_path) -> None:
    server = create_events_server(EventsRuntime(tmp_path))
    public = await server.get_tool("events_publish")
    for event_type in ("graph.projection.requested", "dev_loop.cycle.completed"):
        result = public.fn(event_type=event_type, payload={}, source="attacker")
        assert result.ok is False
        assert result.error == "protected_event_requires_service"
    protected = await server.get_tool("events_publish_projection")
    with pytest.raises(ServiceOnlyAccessError):
        protected.fn(
            tenant_id="tenant", owner_id="owner",
            event_type="graph.projection.requested", subject_id="lesson-1",
            revision=1, payload_digest="a" * 64, record=_record(),
        )


def test_trusted_projection_reaches_graph_through_exact_service_claims(tmp_path) -> None:
    events = EventsRuntime(tmp_path)
    graph_runtime = GraphRuntime({"default_backend": "networkx"})
    aggregator = MCPAggregator()
    aggregator.set_available_bricks(["events", "graph"])
    aggregator._lazy._cache["events"] = create_events_server(events)
    aggregator._lazy._cache["graph"] = create_graph_server(graph_runtime)
    native = NativeEnvelopeInvoker(aggregator)
    previous_factory = get_service("tool_invoker_for_caller")
    previous_invoker = get_service("tool_invoker")
    set_service("tool_invoker_for_caller", native.for_caller)
    set_service("tool_invoker", aggregator.invoke_tool)
    record = _record()
    digest = hashlib.sha256(protected_canonical_json(record)).hexdigest()
    binding = {
        "tenant_id": "tenant", "owner_id": "owner",
        "event_type": "graph.projection.requested",
        "subject_id": "lesson-1", "revision": 1,
        "payload_digest": digest,
    }
    try:
        result = native.for_caller("lessons")(
            {"brick_name": "events", "tool_name": "events_publish_projection"},
            arguments={**binding, "record": record},
            idempotency_key="lesson-projection:lesson-1:1",
            envelope={"tenant_id": "tenant", "principal_id": "owner"},
            projection=binding,
        )
        assert result["ok"] is True
        subject = encode_node_id("lesson", "tenant", "owner", "lesson-1")
        deadline = time.monotonic() + 2
        while graph_runtime.get_graph("networkx").get_entity(subject) is None \
                and time.monotonic() < deadline:
            time.sleep(0.01)
        entity = graph_runtime.get_graph("networkx").get_entity(subject)
        assert entity is not None and entity.properties["source_system"] == "lessons"
    finally:
        set_service("tool_invoker_for_caller", previous_factory)
        set_service("tool_invoker", previous_invoker)


def test_attested_dev_loop_cycles_score_with_distinct_durable_keys(tmp_path) -> None:
    from factory.mcp_utils.interface import ToolResult

    events = EventsRuntime(tmp_path)
    aggregator = MCPAggregator()
    aggregator.set_available_bricks(["events"])
    aggregator._lazy._cache["events"] = create_events_server(events)
    native = NativeEnvelopeInvoker(aggregator)

    def learning(tool_name, **kwargs):
        if tool_name == "learning_compute_reward":
            return ToolResult(ok=True, data={
                "signals": [], "source_id": "llm-judge", "scalar": 0.8,
                "verdict": "rewarded", "reward_value": 80.0,
                "wallet_id": "wallet-kiro-agent", "provenance": {},
                "raw": {}, "scoring": {"f1": 0.8},
            }).model_dump(mode="json")
        if tool_name == "events_query_events":
            return {"events": []}
        if tool_name == "events_publish":
            return {"event_id": "reward", "status": "published"}
        return {}

    previous = get_service("tool_invoker")
    set_service("tool_invoker", learning)
    keys = []
    try:
        for cycle in ("goal:1", "goal:2"):
            material = {
                "loop_id": "goal", "cycle_id": cycle,
                "workflow_run_id": f"run-{cycle[-1]}",
                "report_digest": "b" * 64,
                "input_summary": "complete the development task",
                "output_summary": "Completed the development cycle with verified tests and evidence.",
            }
            digest = hashlib.sha256(protected_canonical_json(material)).hexdigest()
            binding = {
                "tenant_id": "tenant", "owner_id": "owner",
                "event_type": "dev_loop.cycle.completed", "subject_id": cycle,
                "revision": 2, "payload_digest": digest,
            }
            result = native.for_caller("workflow")(
                {"brick_name": "events", "tool_name": "events_score_dev_loop_cycle"},
                arguments={**binding, **material},
                idempotency_key=f"score:{cycle}",
                envelope={"tenant_id": "tenant", "principal_id": "owner"},
                projection=binding,
            )
            data = result["result"]["structured_content"]["data"]
            assert data["scored"] is True
            assert data["reward"]["tenant_id"] == "tenant"
            assert data["reward"]["principal_id"] == "owner"
            keys.append(data["reward"]["idempotency_key"])
        assert keys[0] != keys[1]
        assert all("goal" in key for key in keys)
    finally:
        set_service("tool_invoker", previous)
