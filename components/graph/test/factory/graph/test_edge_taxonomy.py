"""Tests for the edge mesh-workflow taxonomy extension.

Vocabulary source:
``projects/companion_x/experiments/edge_models/edge-mesh-workflow-design/``
(design.md §2 collections + edge-cases.md C1-C7). Structure mirrors
``test_can_failure_taxonomy.py``: surface re-exports, data shape,
registry resolution, MCP resource. Covers taxonomy shape + registry
surface only — no end-to-end graph-query file yet (add one when a
consumer materializes edge nodes).
"""

import asyncio
import json

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from factory.graph.interface import (
    EDGE_CONVENTIONS,
    EDGE_DOMAIN_ID,
    EDGE_NODE_TYPES,
    EDGE_RELATIONSHIP_TYPES,
    create_server,
    register_can_failure_taxonomy,
    register_edge_taxonomy,
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


def test_interface_reexports_edge_constants() -> None:
    """Cross-brick consumers import from ``factory.graph.interface``."""
    assert EDGE_DOMAIN_ID == "edge"
    assert {"EdgeDevice", "EdgeWorkflow", "EdgeObservation"} <= set(EDGE_NODE_TYPES)
    assert "EDGE_VERIFY_FOR" in EDGE_RELATIONSHIP_TYPES
    assert EDGE_CONVENTIONS["domain"] == "edge"
    assert callable(register_edge_taxonomy)


def test_register_edge_appends_to_registry() -> None:
    """The convenience function reaches the same registry as raw API."""
    register_edge_taxonomy()
    extensions = get_extensions()
    assert EDGE_DOMAIN_ID in extensions
    assert "EdgeClaim" in extensions[EDGE_DOMAIN_ID]["node_types"]
    assert "EDGE_JOURNALED" in extensions[EDGE_DOMAIN_ID]["relationship_types"]


# ----- 2. Shape of the taxonomy data --------------------------------------


REQUIRED_NODE_TYPES = {
    "EdgeDevice", "EdgeWorkflow", "EdgeClaim", "EdgeResult",
    "EdgeTransition", "EdgeObservation",
}
REQUIRED_REL_TYPES = {
    "EDGE_OBSERVED_ON", "EDGE_TARGETS", "EDGE_TRIGGERED_BY",
    "EDGE_CLAIMED_BY", "EDGE_PRODUCED", "EDGE_JOURNALED",
    "EDGE_VERIFY_FOR",
}


def test_all_required_edge_node_types_declared() -> None:
    """Design.md §2 mandates the full node-type set (one per collection + journal)."""
    assert REQUIRED_NODE_TYPES.issubset(EDGE_NODE_TYPES.keys())


def test_all_required_edge_relationship_types_declared() -> None:
    """All seven mesh-workflow edges, including the C7 verify predicate."""
    assert REQUIRED_REL_TYPES.issubset(EDGE_RELATIONSHIP_TYPES.keys())


def test_each_node_type_has_required_fields() -> None:
    """Every node spec carries description / required / id_convention."""
    for node, spec in EDGE_NODE_TYPES.items():
        assert "description" in spec, f"{node} missing description"
        assert "required_properties" in spec, f"{node} missing required_properties"
        assert "id_convention" in spec, f"{node} missing id_convention"
        assert "id_example" in spec, f"{node} missing id_example"
        assert spec["required_properties"], f"{node} has empty required_properties"


def test_epistemic_status_is_optional_convention_on_every_node() -> None:
    """The session's labeling discipline: harness-proven|sdk-live|convention|q1-gap."""
    for node, spec in EDGE_NODE_TYPES.items():
        assert "epistemic_status" in spec["optional_properties"], f"{node} missing"
        assert "epistemic_status" not in spec["required_properties"]
        assert {"harness-proven", "sdk-live", "convention", "q1-gap"} <= set(
            EDGE_CONVENTIONS["epistemic_status"].split()
        )


def test_id_conventions_are_content_addressed() -> None:
    """Design.md _id derivations: sha256 content addressing, never LWW slots."""
    for node in ("EdgeWorkflow", "EdgeClaim", "EdgeResult", "EdgeTransition", "EdgeObservation"):
        assert "sha256" in EDGE_NODE_TYPES[node]["id_convention"], f"{node} not content-addressed"


def test_each_relationship_has_source_and_target() -> None:
    """Every relationship spec carries source / target constraints."""
    for rel, spec in EDGE_RELATIONSHIP_TYPES.items():
        assert spec["source"], f"{rel} empty source"
        assert spec["target"], f"{rel} empty target"


@given(rel_name=st.sampled_from(sorted(EDGE_RELATIONSHIP_TYPES)))
@SETTINGS
def test_relationship_endpoints_reference_known_node_types(rel_name: str) -> None:
    """Every edge relationship has at least one endpoint that is an edge node.

    Pipe-delimited alternatives are allowed (matches the
    ``EXT_RELATIONSHIP_TYPES`` pattern).
    """
    spec = EDGE_RELATIONSHIP_TYPES[rel_name]
    edge_nodes = set(EDGE_NODE_TYPES)
    source_ends = {s.strip() for s in spec["source"].split("|")}
    target_ends = {t.strip() for t in spec["target"].split("|")}
    assert source_ends & edge_nodes or target_ends & edge_nodes, (
        f"{rel_name} has no edge endpoint: source={spec['source']!r} target={spec['target']!r}"
    )


def test_entity_id_conventions_match_node_id_conventions() -> None:
    """The conventions block is derived from the node-type spec."""
    for node, spec in EDGE_NODE_TYPES.items():
        assert EDGE_CONVENTIONS["entity_id_conventions"][node] == spec["id_convention"]
        assert EDGE_CONVENTIONS["id_examples"][node] == spec["id_example"]


# ----- 3. Registry resolution ---------------------------------------------


def test_resolve_edge_returns_edge_types() -> None:
    """Resolve returns the edge extension AND the security base."""
    register_edge_taxonomy()
    result = resolve_domain_taxonomy("edge")
    assert "EdgeDevice" in result["node_types"]
    assert "EDGE_VERIFY_FOR" in result["relationship_types"]
    # Security base also present (security seeds the base)
    assert "Finding" in result["node_types"]
    assert "DISCOVERED" in result["relationship_types"]


def test_register_edge_collision_raises() -> None:
    """Append-only contract: re-registering the same domain raises."""
    register_edge_taxonomy()
    with pytest.raises(ValueError, match="already registered"):
        register_edge_taxonomy()


def test_registering_edge_does_not_mutate_security_default() -> None:
    """Strict canary: registering edge must not leak into security view."""
    register_edge_taxonomy()
    sec = resolve_domain_taxonomy("security")
    assert "EdgeDevice" not in sec["node_labels"]
    assert "EdgeWorkflow" not in sec["node_labels"]


def test_can_failure_and_edge_can_coexist() -> None:
    """Two domains register side by side; resolution stays scoped."""
    register_can_failure_taxonomy()
    register_edge_taxonomy()
    assert "EdgeDevice" in resolve_domain_taxonomy("edge")["node_types"]
    assert "Vehicle" not in resolve_domain_taxonomy("edge")["node_types"]


# ----- 4. MCP resource surface --------------------------------------------


def test_edge_taxonomy_exposed_via_mcp_resource() -> None:
    """``graph://schemas/taxonomy/edge`` returns the merged view."""
    register_edge_taxonomy()
    server = create_server()

    async def _read() -> str:
        result = await server.read_resource("graph://schemas/taxonomy/edge")
        return result.contents[0].content

    payload = json.loads(asyncio.run(_read()))
    assert {"EdgeDevice", "EdgeObservation"} <= set(payload["node_types"])
    assert "EDGE_VERIFY_FOR" in payload["relationship_types"]
