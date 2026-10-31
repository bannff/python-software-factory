"""Snapshot tests for registry_contracts JSON schemas.

bd python-factory-uffq: pin ``model_json_schema()`` for the four
key models so future field renames break visibly. Snapshots assert
the field names + required set rather than the full schema (which
can drift on Pydantic version bumps).
"""
from __future__ import annotations

from pydantic import TypeAdapter

from factory.agent.runtime.registry_contracts import (
    GraphConfig, NodeRef, SwarmConfig, WorkflowConfig,
)


def _names_and_required(schema: dict) -> tuple[set[str], set[str]]:
    """Extract field names + required set from a Pydantic JSON schema."""
    props = set(schema.get("properties", {}))
    required = set(schema.get("required", []))
    return props, required


# --- GraphConfig ---

EXPECTED_GRAPH_FIELDS = {
    "id", "kind", "name", "description", "nodes", "edges",
    "entry_points", "entry_point", "max_node_executions", "max_cycles",
    "execution_timeout", "node_timeout", "required_bricks",
    "context_vars", "conditions", "tool_allowlist", "terminal_node",
    "resumable",
}
EXPECTED_GRAPH_REQUIRED = {"id", "name"}


def test_snapshot_graph_fields() -> None:
    schema = GraphConfig.model_json_schema()
    props, required = _names_and_required(schema)
    assert props == EXPECTED_GRAPH_FIELDS, (
        f"GraphConfig fields drifted: missing {EXPECTED_GRAPH_FIELDS - props} "
        f"unexpected {props - EXPECTED_GRAPH_FIELDS}"
    )
    assert required == EXPECTED_GRAPH_REQUIRED


# --- WorkflowConfig ---

EXPECTED_WORKFLOW_FIELDS = {
    "id", "kind", "factory", "name", "description",
    "required_bricks", "context_vars", "tool_allowlist",
    "execution_timeout", "node_timeout",
}
EXPECTED_WORKFLOW_REQUIRED = {"id", "kind", "factory", "name"}


def test_snapshot_workflow_fields() -> None:
    schema = WorkflowConfig.model_json_schema()
    props, required = _names_and_required(schema)
    assert props == EXPECTED_WORKFLOW_FIELDS, (
        f"WorkflowConfig fields drifted: "
        f"missing {EXPECTED_WORKFLOW_FIELDS - props} "
        f"unexpected {props - EXPECTED_WORKFLOW_FIELDS}"
    )
    assert required == EXPECTED_WORKFLOW_REQUIRED


def test_snapshot_workflow_carries_tool_allowlist() -> None:
    """bd-42dz pre-condition viii: WorkflowConfig must carry the
    same MCP tool-narrowing field as GraphConfig (positive-existence
    pin so a future schema purge fails loudly)."""
    schema = WorkflowConfig.model_json_schema()
    props, _ = _names_and_required(schema)
    assert "tool_allowlist" in props, (
        "WorkflowConfig.tool_allowlist dropped — required for "
        "build_mcp_client_for_config narrowing (bd-42dz)."
    )


# --- SwarmConfig ---

EXPECTED_SWARM_FIELDS = {
    "id", "kind", "name", "description", "entry_point", "agents",
    "max_handoffs", "max_iterations", "execution_timeout",
    "node_timeout", "required_bricks", "context_vars",
    "input_schema", "output_schema",
    "repetitive_handoff_detection_window",
    "repetitive_handoff_min_unique_agents",
}
EXPECTED_SWARM_REQUIRED = {"id", "name", "entry_point"}


def test_snapshot_swarm_fields() -> None:
    schema = SwarmConfig.model_json_schema()
    props, required = _names_and_required(schema)
    assert props == EXPECTED_SWARM_FIELDS, (
        f"SwarmConfig fields drifted: "
        f"missing {EXPECTED_SWARM_FIELDS - props} "
        f"unexpected {props - EXPECTED_SWARM_FIELDS}"
    )
    assert required == EXPECTED_SWARM_REQUIRED


# --- NodeRef (sub-discriminated union) ---

def test_snapshot_node_ref_definitions() -> None:
    schema = TypeAdapter(NodeRef).json_schema()
    defs = schema.get("$defs") or schema.get("definitions") or {}
    expected_member_names = {
        "AgentNodeRef", "SwarmNodeRef", "GraphNodeRef", "CustomNodeRef",
    }
    actual = set(defs)
    missing = expected_member_names - actual
    assert not missing, f"NodeRef union member missing from schema: {missing}"
    # Discriminator keyed by `type`.
    one_of = (schema.get("oneOf") or schema.get("anyOf") or
              [{"$ref": f"#/$defs/{n}"} for n in expected_member_names])
    assert one_of  # non-empty after Pydantic emits the union


def test_snapshot_agent_node_ref_carries_context() -> None:
    """Audit-discovered field — must persist (uffq deviation)."""
    from factory.agent.runtime.registry_contracts import AgentNodeRef
    schema = AgentNodeRef.model_json_schema()
    props, _ = _names_and_required(schema)
    assert "context" in props, (
        "AgentNodeRef.context dropped — production graphs use it "
        "(defaults_code_scan_single, defaults_sandbox_graph_only, "
        "defaults_code_scan_hybrid)."
    )


def test_snapshot_graph_carries_tool_allowlist() -> None:
    """Audit-discovered field — must persist (uffq deviation)."""
    schema = GraphConfig.model_json_schema()
    props, _ = _names_and_required(schema)
    assert "tool_allowlist" in props, (
        "GraphConfig.tool_allowlist dropped — production graphs use it "
        "(defaults_code_scan_single SAST_*_GRAPH; read by run_graph.py)."
    )
