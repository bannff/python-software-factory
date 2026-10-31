"""Focused materialization replay and legacy fan-out contracts."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from factory.graph.runtime.runtime import GraphRuntime
from factory.graph.server import create_mcp_server
from factory.mcp_utils.interface import get_envelope, get_service, set_service
from factory.telemetry.runtime.provenance_models import (
    AuthenticatedTelemetryContext,
    MappingActivationRecord,
    MaterializationMapping,
    TelemetryIngestBatch,
    TelemetryIngestItem,
    TelemetryMaterialize,
)
from factory.telemetry.runtime.provenance_runtime import TelemetryProvenanceRuntime
from factory.telemetry.runtime.provenance_store import JsonProvenanceStore


def _context() -> AuthenticatedTelemetryContext:
    return AuthenticatedTelemetryContext(
        tenant_id="tenant-1", producer_id="producer-1", principal_id="principal-1",
        visibility="private", source_namespace="tests",
    )


def _mapping(fan_out: int = 2) -> MaterializationMapping:
    return MaterializationMapping(
        mapping_id="graph", version="1", accepted_signals=("span",),
        target_brick="graph", target_capability="graph_write_relationship",
        target_version="1", max_fan_out=fan_out,
    )


def _activate(runtime: TelemetryProvenanceRuntime, mapping: MaterializationMapping) -> None:
    runtime.activate_mapping(MappingActivationRecord(
        registry_version="1", mappings=(mapping,), edges=(),
        activated_at=datetime.now(timezone.utc),
    ))


@contextmanager
def _legacy_invoker(callback: Any) -> Iterator[None]:
    previous_structured = get_service("tool_invoker_envelope")
    previous_legacy = get_service("tool_invoker")
    set_service("tool_invoker_envelope", None)
    set_service("tool_invoker", callback)
    try:
        yield
    finally:
        set_service("tool_invoker_envelope", previous_structured)
        set_service("tool_invoker", previous_legacy)


def test_legacy_multi_fan_out_gets_distinct_keys_and_reopens_completed_store(tmp_path) -> None:
    path = tmp_path / "provenance.sqlite3"
    runtime = TelemetryProvenanceRuntime(
        JsonProvenanceStore(path), target_resolver=lambda target: target.version,
    )
    _activate(runtime, _mapping())
    accepted = runtime.ingest(TelemetryIngestBatch(
        batch_id="batch-1",
        items=[TelemetryIngestItem(
            source_id="source-1", canonical_payload={"value": 1}, signal="span",
        )],
    ), _context())
    reference = accepted.outcomes[0].telemetry_ref
    assert reference is not None
    calls: list[dict[str, Any]] = []
    graph_server = create_mcp_server(GraphRuntime({"default_backend": "networkx"}))
    graph_tool = asyncio.run(graph_server.get_tool("graph_write_relationship")).fn

    def invoke(tool_name: str, **kwargs: Any) -> Any:
        calls.append({
            "tool_name": tool_name, "arguments": dict(kwargs),
            "envelope": dict(get_envelope() or {}),
        })
        result = graph_tool(**kwargs)
        assert result.ok
        return result

    request = TelemetryMaterialize(
        telemetry_ids=[reference], mappings=[("graph", "1")],
    )
    with _legacy_invoker(invoke):
        result = runtime.materialize(request, _context())

    prefix = f"telemetry-materialize:{reference}:graph:1"
    assert result.materialized == 1
    assert [call["tool_name"] for call in calls] == [
        "graph_write_relationship", "graph_write_relationship",
    ]
    assert all("idempotency_key" not in call["arguments"] for call in calls)
    assert [call["envelope"]["attributes"]["workflow_attempt_id"] for call in calls] == [
        f"{prefix}:0", f"{prefix}:1",
    ]
    payloads = [call["arguments"] for call in calls]
    assert payloads[0] == payloads[1]

    reopened = JsonProvenanceStore(path)
    assert reopened.has_materialization_completion(reference, "graph", "1", 0)
    assert reopened.has_materialization_completion(reference, "graph", "1", 1)
    restored = TelemetryProvenanceRuntime(reopened)
    replay = restored.materialize(request, _context())
    assert replay.materialized == 0
    assert replay.outcomes[0].reason == "already_materialized"
