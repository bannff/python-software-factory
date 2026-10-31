"""Tests for the CAN failure-prediction taxonomy extension.

Epic python-factory-can-failure. The C1 canary from
``.github/spec/can-failure-prediction.md`` is the headline test —
``resolve_domain_taxonomy("can_failure")`` returns CAN node / rel types
without security base pollution, then the merge returns CAN types WITH
the security base.

This file covers the **taxonomy shape + registry surface**. The
end-to-end graph-query check ("find all FailureModes for Vehicle X")
lives in ``test_can_failure_taxonomy_graph.py`` so each file stays
under the 200 LOC budget.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from factory.graph.interface import (
    CAN_FAILURE_CONVENTIONS,
    CAN_FAILURE_DOMAIN_ID,
    CAN_FAILURE_NODE_TYPES,
    CAN_FAILURE_RELATIONSHIP_TYPES,
    create_server,
    register_can_failure_taxonomy,
)
from factory.graph.runtime.taxonomy_registry import (
    get_extensions,
    resolve_domain_taxonomy,
    reset_extensions,
)


SETTINGS = settings(
    max_examples=20, deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


@pytest.fixture(autouse=True)
def _isolation():
    """Wipe the registry around every test (append-only contract)."""
    reset_extensions()
    yield
    reset_extensions()


# ----- 1. Surface / cross-brick re-exports -------------------------------


def test_interface_reexports_can_failure_constants() -> None:
    """Cross-brick consumers import from ``factory.graph.interface``."""
    assert CAN_FAILURE_DOMAIN_ID == "can_failure"
    assert "Vehicle" in CAN_FAILURE_NODE_TYPES
    assert "FailureMode" in CAN_FAILURE_NODE_TYPES
    assert "PRECEDES_FAILURE" in CAN_FAILURE_RELATIONSHIP_TYPES
    assert CAN_FAILURE_CONVENTIONS["domain"] == "can_failure"
    assert callable(register_can_failure_taxonomy)


def test_register_can_failure_appends_to_registry() -> None:
    """The convenience function reaches the same registry as raw API."""
    register_can_failure_taxonomy()
    extensions = get_extensions()
    assert CAN_FAILURE_DOMAIN_ID in extensions
    assert "Vehicle" in extensions[CAN_FAILURE_DOMAIN_ID]["node_types"]
    assert "REPAIRED_BY" in extensions[CAN_FAILURE_DOMAIN_ID]["relationship_types"]


# ----- 2. Shape of the taxonomy data --------------------------------------


REQUIRED_NODE_TYPES = {
    "Vehicle", "Trip", "CANBus", "ECU", "Frame", "Signal",
    "DBCVersion", "DTC", "FailureMode", "MaintenanceEvent",
}
REQUIRED_REL_TYPES = {
    "HAS_ECU", "PART_OF_TRIP", "EMITS_FRAME", "DECODES_TO",
    "CORRELATES_WITH", "PRECEDES_FAILURE", "REPAIRED_BY", "ANNOTATED_AS",
}


def test_all_required_can_node_types_declared() -> None:
    """Spec §2.1 mandates the full node-type set."""
    assert REQUIRED_NODE_TYPES.issubset(CAN_FAILURE_NODE_TYPES.keys())


def test_all_required_can_relationship_types_declared() -> None:
    """Spec §2.1 mandates the full relationship-type set."""
    assert REQUIRED_REL_TYPES.issubset(CAN_FAILURE_RELATIONSHIP_TYPES.keys())


def test_each_node_type_has_required_fields() -> None:
    """Every node spec carries description / required / id_convention."""
    for node, spec in CAN_FAILURE_NODE_TYPES.items():
        assert "description" in spec, f"{node} missing description"
        assert "required_properties" in spec, f"{node} missing required_properties"
        assert "id_convention" in spec, f"{node} missing id_convention"
        assert "id_example" in spec, f"{node} missing id_example"
        assert isinstance(spec["required_properties"], list)
        assert spec["required_properties"], f"{node} has empty required_properties"


def test_each_relationship_has_source_and_target() -> None:
    """Every relationship spec carries source / target constraints."""
    for rel, spec in CAN_FAILURE_RELATIONSHIP_TYPES.items():
        assert "source" in spec, f"{rel} missing source"
        assert "target" in spec, f"{rel} missing target"
        assert spec["source"], f"{rel} empty source"
        assert spec["target"], f"{rel} empty target"


@given(rel_name=st.sampled_from(sorted(CAN_FAILURE_RELATIONSHIP_TYPES)))
@SETTINGS
def test_relationship_endpoints_reference_known_node_types(rel_name: str) -> None:
    """The source / target of every CAN relationship references a known node.

    Pipe-delimited alternatives are allowed (matches the
    ``EXT_RELATIONSHIP_TYPES`` pattern). At least one endpoint of every
    CAN relationship must resolve to a CAN node.
    """
    spec = CAN_FAILURE_RELATIONSHIP_TYPES[rel_name]
    can_nodes = set(CAN_FAILURE_NODE_TYPES)
    source_ends = {s.strip() for s in spec["source"].split("|")}
    target_ends = {t.strip() for t in spec["target"].split("|")}
    assert source_ends & can_nodes or target_ends & can_nodes, (
        f"{rel_name} has no CAN endpoint: "
        f"source={spec['source']!r} target={spec['target']!r}"
    )


def test_entity_id_conventions_match_node_id_conventions() -> None:
    """The conventions block is derived from the node-type spec."""
    for node, spec in CAN_FAILURE_NODE_TYPES.items():
        assert CAN_FAILURE_CONVENTIONS["entity_id_conventions"][node] == spec["id_convention"]
        assert CAN_FAILURE_CONVENTIONS["id_examples"][node] == spec["id_example"]


# ----- 3. Registry resolution (C1 canary) --------------------------------


def test_resolve_can_failure_returns_can_types() -> None:
    """C1 canary: resolve returns the CAN extension AND the security base.

    Per meta-architect verdict 2efd2a40 Q3, one extension at a time,
    security always seeds the base.
    """
    register_can_failure_taxonomy()
    result = resolve_domain_taxonomy("can_failure")
    assert result is not None
    # CAN extension present
    assert "Vehicle" in result["node_types"]
    assert "FailureMode" in result["node_types"]
    assert "PRECEDES_FAILURE" in result["relationship_types"]
    # Security base also present (per Q3 verdict — security seeds the base)
    assert "Finding" in result["node_types"]
    assert "DISCOVERED" in result["relationship_types"]


def test_register_can_failure_collision_raises() -> None:
    """Append-only contract: re-registering the same domain raises."""
    register_can_failure_taxonomy()
    with pytest.raises(ValueError, match="already registered"):
        register_can_failure_taxonomy()


def test_registering_can_failure_does_not_mutate_security_default() -> None:
    """C1 strict canary: registering CAN must not leak into security view."""
    register_can_failure_taxonomy()
    sec = resolve_domain_taxonomy("security")
    assert "Vehicle" not in sec["node_labels"]
    assert "FailureMode" not in sec["node_labels"]


# ----- 4. MCP resource surface (C1 cross-check) --------------------------


def test_can_failure_taxonomy_exposed_via_mcp_resource() -> None:
    """``graph://schemas/taxonomy/can_failure`` returns the merged view."""
    register_can_failure_taxonomy()
    server = create_server()

    async def _read() -> str:
        result = await server.read_resource("graph://schemas/taxonomy/can_failure")
        return result.contents[0].content

    body = asyncio.run(_read())
    payload = json.loads(body)
    assert "Vehicle" in payload["node_types"]
    assert "FailureMode" in payload["node_types"]
    assert "PRECEDES_FAILURE" in payload["relationship_types"]
