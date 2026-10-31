"""Pydantic round-trip + discriminator + extra-forbidden tests for the
activity-message contracts (bd:python-factory-6zyg).

Asserts the union routes correctly on ``activityType`` and that
``extra="forbid"`` blocks SDK-shape leaks. Includes a JSON schema
fixture that exists so a future FE Zod schema sync (or a contract
generator) can dump the same fields and diff them.
"""
from __future__ import annotations

import json

import pytest
from pydantic import TypeAdapter, ValidationError

from factory.ui.runtime.ag_ui_activity_models import (
    NodeActivity, SubagentActivity,
    SubagentGraphActivity, SubagentSwarmActivity,
)


def test_swarm_round_trip() -> None:
    body = SubagentSwarmActivity(
        run_id="r1", swarm_id="r1", status="running",
        agent_count=2, started_at=1.0,
    ).model_dump(mode="json")
    assert body["activityType"] == "subagent.swarm"
    assert SubagentSwarmActivity.model_validate(body).swarm_id == "r1"


def test_graph_round_trip() -> None:
    body = SubagentGraphActivity(
        run_id="r2", graph_id="r2", status="running",
        started_at=2.5, nodes=[NodeActivity(node_id="n1", status="running")],
    ).model_dump(mode="json")
    assert body["activityType"] == "subagent.graph"
    assert SubagentGraphActivity.model_validate(body).nodes[0].status == "running"


def test_discriminated_union_routes_swarm_and_graph() -> None:
    adapter = TypeAdapter(SubagentActivity)
    swarm = adapter.validate_python({
        "activityType": "subagent.swarm", "run_id": "r3",
        "swarm_id": "r3", "status": "running",
        "agent_count": 0, "started_at": 1.0,
    })
    graph = adapter.validate_python({
        "activityType": "subagent.graph", "run_id": "r4",
        "graph_id": "r4", "status": "completed",
        "started_at": 1.0, "completed_at": 5.0,
    })
    assert isinstance(swarm, SubagentSwarmActivity)
    assert isinstance(graph, SubagentGraphActivity)


def test_discriminator_unknown_value_raises() -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(SubagentActivity).validate_python({
            "activityType": "subagent.unknown",
            "run_id": "r5", "status": "running", "started_at": 1.0,
        })


def test_extra_forbid_on_swarm_and_node() -> None:
    with pytest.raises(ValidationError):
        SubagentSwarmActivity(
            run_id="r6", swarm_id="r6", status="running",
            agent_count=1, started_at=1.0, sneaky="x",  # type: ignore[call-arg]
        )
    with pytest.raises(ValidationError):
        NodeActivity(node_id="n1", status="running",
                      extra="leak")  # type: ignore[call-arg]


def test_status_enum_validation() -> None:
    with pytest.raises(ValidationError):
        NodeActivity(node_id="n2", status="weird")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        SubagentSwarmActivity(
            run_id="r7", swarm_id="r7",
            status="weird",  # type: ignore[arg-type]
            agent_count=0, started_at=1.0,
        )


def test_json_schema_dump_fixture() -> None:
    """Schema dump diff fixture for downstream FE Zod sync."""
    schema = TypeAdapter(SubagentActivity).json_schema()
    text = json.dumps(schema, sort_keys=True)
    assert '"subagent.swarm"' in text
    assert '"subagent.graph"' in text
    assert '"NodeActivity"' in text or "node_id" in text
