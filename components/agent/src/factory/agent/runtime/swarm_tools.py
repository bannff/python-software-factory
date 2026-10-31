"""Focused MCP tool allowlist for swarm agents.

Keeps the tool list small (~30 tools) so strands native tools
(think, http_request, etc) don't get buried by 200+ MCP tools.

bd python-factory-nx4v (L3): added typed graph reads
(``graph_get_findings_for_run``, ``graph_count_entities_by_run``,
``graph_get_workflow_summary``, ``graph_get_recent_findings``,
``graph_get_target_app``, ``graph_get_tool_invocations_for_run``)
plus ``security_list_findings_for_run`` so swarm agents can answer
run-scoped queries without writing backend-specific queries.
"""
from __future__ import annotations

SWARM_TOOL_ALLOWLIST: set[str] = {
    # Sandbox operations (both dot and underscore conventions)
    "sandbox.execute", "sandbox_execute",
    "sandbox.list_environments", "sandbox_list_environments",
    "sandbox.describe_stack", "sandbox_describe_stack",
    "sandbox.list_stacks", "sandbox_list_stacks",
    "sandbox.deploy_cfn", "sandbox_deploy_cfn",
    "sandbox.delete_stack", "sandbox_delete_stack",
    # Security pentest (both conventions)
    "security_pentest_scan", "security_pentest_status",
    "security_pentest_results",
    "security.code_review", "security.threat_model",
    "security.recon",
    "security.scan_endpoints", "security.trace_taint",
    "security.classify_confidence",
    "security_classify_finding",
    # Security typed reads (run-scoped)
    "security_list_findings_for_run",
    "graph_add_entity", "graph_add_relationship",
    # Graph — typed reads (backend-agnostic; bd python-factory-nx4v)
    "graph_find_entities", "graph_get_entity",
    "graph_get_findings_for_run",
    "graph_count_entities_by_run",
    "graph_get_workflow_summary",
    "graph_get_recent_findings",
    "graph_get_target_app",
    "graph_get_tool_invocations_for_run",
    # Memory (learnings only)
    "memory_store", "memory_retrieve",
    # KB (proven findings — ingest + search)
    "kb_ingest", "ingest", "search",
    # Builder (code access)
    # Skills
    "skills",
    # Events
    "events_publish",
    # Evals (LLMAJ grading)
    "evals_evaluate", "evals_evaluate_multi",
    "evals_evaluate_session",
    # Games (RL rewards)
    "games_create", "games_security_move",
    "games_process_finished", "games_evaluate",
    # Logging
    "logger_info",
}
