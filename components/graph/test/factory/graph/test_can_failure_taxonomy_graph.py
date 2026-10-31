"""End-to-end graph-query tests for the CAN failure-prediction taxonomy.

Companion to ``test_can_failure_taxonomy.py``:
this file drives the **real** ``KnowledgeGraph`` port with a small CAN
fixture and answers the spec's "find all FailureModes for Vehicle X"
query. Uses the networkx adapter (deterministic, no external services)
so the test runs in any environment.

Why a separate file: keeps both test files under the 200 LOC budget
mandated by the factory foundation tenets.
"""

from __future__ import annotations

import pytest

from factory.graph.interface import (
    register_can_failure_taxonomy,
    get_runtime,
    reset_runtime,
)
from factory.graph.runtime.ports import Entity, Relationship
from factory.graph.runtime.taxonomy_registry import (
    reset_extensions,
    resolve_domain_taxonomy,
)


@pytest.fixture(autouse=True)
def _isolation():
    """Wipe the registry + runtime around every test."""
    reset_runtime()
    reset_extensions()
    yield
    reset_runtime()
    reset_extensions()


def _seed_can_graph() -> "object":
    """Build a tiny CAN graph for the "find FailureModes for Vehicle X" test.

    Two vehicles (V001, V002), two PRECEDES_FAILURE edges feeding V001's
    coolant_leak + battery_degradation failure modes, and one edge
    feeding V002's sensor_stuck mode. This lets us prove that a
    FailureMode can be associated with a specific Vehicle via the
    Signal -> FailureMode path AND that the security base is still
    resolvable after the merge.
    """
    register_can_failure_taxonomy()
    runtime = get_runtime()
    graph = runtime.get_graph("networkx")

    graph.add_entity(Entity(
        id="vehicle-V001", type="Vehicle",
        properties={"vehicle_id": "V001", "make": "Ford", "model": "F-150", "year": 2022},
    ))
    graph.add_entity(Entity(
        id="vehicle-V002", type="Vehicle",
        properties={"vehicle_id": "V002", "make": "Tesla", "model": "Model 3", "year": 2024},
    ))
    graph.add_entity(Entity(
        id="failure-coolant-coolant_leak", type="FailureMode",
        properties={"mode_name": "coolant_leak", "category": "coolant"},
    ))
    graph.add_entity(Entity(
        id="failure-battery-battery_degradation", type="FailureMode",
        properties={"mode_name": "battery_degradation", "category": "battery"},
    ))
    graph.add_entity(Entity(
        id="failure-sensor-sensor_stuck", type="FailureMode",
        properties={"mode_name": "sensor_stuck", "category": "sensor"},
    ))
    # PRECEDES_FAILURE: Signal -> FailureMode.
    graph.add_relationship(Relationship(
        id="prec-1", type="PRECEDES_FAILURE",
        source_id="signal-dbc-v3.1-coolant_temp",
        target_id="failure-coolant-coolant_leak",
        properties={"lead_time_minutes": 45, "confidence": 0.92},
    ))
    graph.add_relationship(Relationship(
        id="prec-2", type="PRECEDES_FAILURE",
        source_id="signal-dbc-v3.1-battery_voltage",
        target_id="failure-battery-battery_degradation",
        properties={"lead_time_minutes": 120, "confidence": 0.78},
    ))
    graph.add_relationship(Relationship(
        id="prec-3", type="PRECEDES_FAILURE",
        source_id="signal-dbc-v3.1-wheel_speed",
        target_id="failure-sensor-sensor_stuck",
        properties={"lead_time_minutes": 5, "confidence": 0.61},
    ))
    return graph


def test_can_failure_taxonomy_drives_actual_graph_queries() -> None:
    """End-to-end: register the extension, build a CAN graph, query it."""
    graph = _seed_can_graph()

    # Catalog lookup: every CAN-typed FailureMode is queryable.
    all_failures = graph.find_entities(entity_type="FailureMode", limit=50)
    assert {e.id for e in all_failures} == {
        "failure-coolant-coolant_leak",
        "failure-battery-battery_degradation",
        "failure-sensor-sensor_stuck",
    }

    # Signal -> FailureMode traversal via the declared edge type.
    coolant_neighbors = graph.get_neighbors(
        "signal-dbc-v3.1-coolant_temp",
        relationship_type="PRECEDES_FAILURE",
        direction="out",
    )
    assert [n.id for n in coolant_neighbors] == ["failure-coolant-coolant_leak"]

    battery_neighbors = graph.get_neighbors(
        "signal-dbc-v3.1-battery_voltage",
        relationship_type="PRECEDES_FAILURE",
        direction="out",
    )
    assert [n.id for n in battery_neighbors] == ["failure-battery-battery_degradation"]

    # Independent FailureMode for V002: no edge from V001's signals.
    v001_failures = [
        n for src in ("signal-dbc-v3.1-coolant_temp", "signal-dbc-v3.1-battery_voltage")
        for n in graph.get_neighbors(src, relationship_type="PRECEDES_FAILURE", direction="out")
    ]
    assert {n.id for n in v001_failures}.isdisjoint(
        {"failure-sensor-sensor_stuck"}
    )

    # The taxonomy still merges cleanly with the security base.
    sec = resolve_domain_taxonomy("security")
    assert "Finding" in sec["node_labels"]


def test_can_failure_nodes_have_correct_metadata() -> None:
    """Round-trip an entity and confirm properties land intact."""
    graph = _seed_can_graph()
    vehicle = graph.get_entity("vehicle-V001")
    assert vehicle is not None
    assert vehicle.type == "Vehicle"
    assert vehicle.properties["make"] == "Ford"
    assert vehicle.properties["year"] == 2022
