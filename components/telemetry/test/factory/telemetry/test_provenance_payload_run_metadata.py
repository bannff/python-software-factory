"""Telemetry-to-Graph browse metadata preserves run provenance safely."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from factory.graph.runtime.provenance_models import GraphRelationshipWrite
from factory.telemetry.runtime.provenance_models import (
    AuthenticatedTelemetryContext, TelemetryIngestItem, TelemetryStoredRecord,
)
from factory.telemetry.runtime.provenance_payload import GraphRelationshipPayload


def _context() -> AuthenticatedTelemetryContext:
    return AuthenticatedTelemetryContext(
        tenant_id="trusted-tenant", producer_id="trusted-producer",
        principal_id="principal", visibility="private", source_namespace="tests",
    )


def _record(attributes: dict) -> TelemetryStoredRecord:
    return TelemetryStoredRecord(
        telemetry_ref="telemetry-ref", context=_context(),
        item=TelemetryIngestItem(
            source_id="span-1", canonical_payload={"name": "node"},
            signal="span", attributes=attributes,
        ),
        retained_at=datetime.now(timezone.utc),
    )


@pytest.mark.parametrize("attributes", [
    {"run_id": "run-a"},
    {"workflow_run_id": "run-a"},
    {"managed_graph.run_id": "run-a"},
    {"managed_graph": {"run_id": "run-a"}},
    {
        "run_id": "run-a", "workflow_run_id": "run-a",
        "managed_graph.run_id": "run-a",
    },
])
def test_nested_attributes_round_trip_with_canonical_root_run_id(attributes: dict) -> None:
    untrusted = {
        **attributes, "tenant_id": "forged", "producer_id": "forged",
        "telemetry_ref": "forged", "source_id": "forged",
    }
    payload = GraphRelationshipPayload.from_record(_record(untrusted), _context())
    write = GraphRelationshipWrite.model_validate(payload.model_dump(mode="json"))

    assert write.browse_metadata["run_id"] == "run-a"
    assert write.browse_metadata["attributes"] == untrusted
    assert write.browse_metadata["tenant_id"] == "trusted-tenant"
    assert write.browse_metadata["producer_id"] == "trusted-producer"
    assert write.browse_metadata["telemetry_ref"] == "telemetry-ref"
    assert write.browse_metadata["source_id"] == "span-1"


@pytest.mark.parametrize("attributes", [
    {"run_id": "run-a", "workflow_run_id": "run-b"},
    {"workflow_run_id": "run-a", "managed_graph.run_id": "run-b"},
    {"run_id": "run-a", "managed_graph": {"run_id": "run-b"}},
])
def test_conflicting_non_empty_run_aliases_are_rejected(attributes: dict) -> None:
    with pytest.raises(ValueError, match="conflicting non-empty run aliases"):
        GraphRelationshipPayload.from_record(_record(attributes), _context())


def test_empty_alias_does_not_conflict_with_non_empty_alias() -> None:
    payload = GraphRelationshipPayload.from_record(
        _record({"run_id": "", "workflow_run_id": "run-a"}), _context(),
    )
    assert payload.browse_metadata["run_id"] == "run-a"
