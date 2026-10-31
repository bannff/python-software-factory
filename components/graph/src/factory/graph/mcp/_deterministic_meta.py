"""Static metadata for portable Graph deterministic tools."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..runtime.runtime import GraphRuntime

_FEATURES = [
    "entity_management", "relationship_management", "path_finding",
    "run_scoped_typed_reads", "recent_tool_invocations", "provenance_projection",
    "taxonomy_edges_polymorphic_reads", "can_failure_taxonomy_autoregistration",
    "canonical_dbc_signal_identity",
]
_RESOURCES = [
    "graph://schemas/node", "graph://schemas/edge", "graph://schemas/taxonomy",
    "graph://schemas/security-taxonomy", "graph://schemas/taxonomy/{domain}",
    "graph://docs/overview", "graph://docs/adapters", "graph://stats",
    "graph://backends", "graph://factory",
]
_PROMPTS = ["create_graph", "query_graph", "import_data", "debug_graph"]
_TOOLS = {
    "deterministic": [
        "graph_get_capabilities", "graph_health_check", "graph_describe_config_schema",
        "graph_get_entity", "graph_get_neighbors", "graph_find_path",
        "graph_find_entities", "graph_get_stats", "graph_get_run_topology",
        "graph_get_findings_for_run", "graph_count_entities_by_run",
        "graph_get_workflow_summary", "graph_get_recent_findings", "graph_get_target_app",
        "graph_get_tool_invocations_for_run", "graph_list_recent_tool_invocations",
        "graph_list_recent_runs", "graph_get_dashboard_summary",
        "graph_get_entity_context", "graph_get_views",
    ],
    "operational": [
        "graph_add_entity", "graph_update_entity", "graph_delete_entity",
        "graph_add_relationship", "graph_delete_relationship", "graph_set_finding_state",
        "graph_write_relationship", "graph_tombstone_relationship", "graph_rebuild",
    ],
    "authoring": [],
}


def capabilities_for(runtime: "GraphRuntime") -> dict:
    """Return the portable Graph capability declaration."""
    return {
        "name": "graph", "version": "1.0.0", "active_backend": runtime.default_backend,
        "backends": runtime.available_backends(),
        "provenance_backends": runtime.provenance_backends(),
        "features": _FEATURES, "tools": _TOOLS,
        "mcp_resources": _RESOURCES, "mcp_prompts": _PROMPTS,
    }
