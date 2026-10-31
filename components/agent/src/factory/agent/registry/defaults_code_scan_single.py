"""SAST code scan — single-model variants for model comparison.

Each graph runs ONE model through the full SAST pipeline:
scanner → validator. Same prompts, tools, and best practices
as the ensemble graph, just isolated per model.

Produces experiment data in challenges/experiments/ for
cross-model comparison (tokens, findings, time, accuracy).

Workflow detail (phases, grounding, finding format) lives in
``skills/<vuln_class>-code-scan/SKILL.md`` and
``skills/<vuln_class>-validate/SKILL.md`` — loaded via the
AgentSkills plugin. See bd python-factory-2xbi.
"""
from __future__ import annotations

from .models import SONNET, NOVA2_LITE, HAIKU
from .vuln_class_config import VULN_CLASS_CONFIG

_VULN_REF = "\n".join(
    f"  {vc}: {cfg['cwe']} ({cfg['owasp_ref']} — {cfg['owasp_name']})"
    for vc, cfg in VULN_CLASS_CONFIG.items()
)

_SCANNER_PROMPT = (
    "You are a SAST code scanner on a security red team.\n"
    "Run ID: {{run_id}} | App: {{target_app}} | "
    "Vuln class: {{vuln_class}} | Workspace: {{sast_workspace}}\n"
    "Agent ID: {{agent_id}}\n\n"
    "Use the `{{vuln_class}}-code-scan` skill for the workflow. "
    "Activate it now via the skills tool, then follow its phases.\n"
    "When done, hand off via the graph protocol.\n\n"
    "CWE/OWASP REFERENCE:\n" + _VULN_REF
)

_VALIDATOR_PROMPT = (
    "You are a finding validator on a security red team.\n"
    "Run ID: {{run_id}} | App: {{target_app}} | "
    "Vuln class: {{vuln_class}} | Workspace: {{sast_workspace}}\n"
    "Agent ID: {{agent_id}}\n\n"
    "Use the `{{vuln_class}}-validate` skill for the workflow. "
    "Activate it now via the skills tool, then follow its phases.\n"
    "When done, store the validation summary."
)

_SCAN_TOOLS = [
    "think", "http_request",
    "file_read", "editor",
    "shell",
]
_VALIDATOR_TOOLS = [
    "think", "file_read",
]

_COMMON = {
    "required_bricks": ["graph", "security", "memory", "kb"],
    "context_vars": [
        "vuln_class", "target_app", "run_id",
        "target_packages", "sast_workspace",
    ],
    "tool_allowlist": [
        # Graph — store/query findings, entities, relationships
        "graph_add_entity", "graph_add_relationship",
        "graph_get_entity",
        # Typed run-scoped reads (backend-agnostic; replace Cypher)
        "graph_find_entities", "graph_get_findings_for_run",
        "graph_count_entities_by_run", "graph_get_workflow_summary",
        "graph_get_recent_findings", "graph_get_target_app",
        "graph_get_tool_invocations_for_run",
        # Security — classify, taint trace, scan endpoints
        "security_classify_finding", "security.classify_confidence",
        "security.trace_taint", "security.scan_endpoints",
        "security_list_findings_for_run",
        # Memory — retrieve learnings, store results
        "memory_retrieve", "memory_store", "memory_hybrid_search",
        # KB — search ground truth, ingest scan results
        "kb_search", "kb_ingest",
    ],
    "max_node_executions": 1,
    "execution_timeout": 2400,
    "node_timeout": 900,
}


def _make_graph(model_id: str, model_tag: str, model_name: str) -> dict:
    """Build a single-model SAST graph: scanner → validator."""
    gid = f"rt-sast-{model_tag}"
    return {
        **_COMMON,
        "id": gid,
        "name": f"SAST Code Scan ({model_name} Solo)",
        "description": (
            f"Single-model SAST: {model_name} scanner → "
            f"{model_name} validator. Same prompts/tools as "
            f"ensemble graph, isolated for comparison."
        ),
        "entry_points": [f"{model_tag}-scanner"],
        "nodes": [
            # bd:python-factory-2tgo1 — single-model variants for IDOR
            # only (only `idor-code-scan` + `idor-validate` SKILL.md
            # exist today).
            {"id": f"{model_tag}-scanner", "type": "agent",
             "model": model_id,
             "description": f"{model_name} SAST scanner.",
             "system_prompt": _SCANNER_PROMPT,
             "tools": _SCAN_TOOLS,
             "skills": ["idor-code-scan"],
             "context": {"agent_id": f"{model_tag}-scanner"}},
            {"id": f"{model_tag}-validator", "type": "agent",
             "model": model_id,
             "description": f"{model_name} finding validator.",
             "system_prompt": _VALIDATOR_PROMPT,
             "tools": _VALIDATOR_TOOLS,
             "skills": ["idor-validate"],
             "context": {"agent_id": f"{model_tag}-validator"}},
        ],
        "edges": [
            {"source": f"{model_tag}-scanner",
             "target": f"{model_tag}-validator"},
        ],
    }


def _make_swarm(model_id: str, model_tag: str, model_name: str) -> dict:
    """Build a single-model SAST swarm: scanner → validator."""
    return {
        "id": f"rt-sast-{model_tag}-swarm",
        "name": f"SAST Code Scan ({model_name} Solo Swarm)",
        "description": (
            f"Sequential swarm: {model_name} scanner → "
            f"{model_name} validator. Handoff-based."
        ),
        "entry_point": f"{model_tag}-scanner",
        "max_handoffs": 4,
        "max_iterations": 20,
        "agents": [
            # bd:python-factory-2tgo1 — IDOR-only (skill SKILL.md
            # files for other vuln_classes don't exist yet).
            {"id": f"{model_tag}-scanner", "model": model_id,
             "description": f"{model_name} SAST scanner.",
             "system_prompt": _SCANNER_PROMPT,
             "skills": ["idor-code-scan"],
             "tools": _SCAN_TOOLS},
            {"id": f"{model_tag}-validator", "model": model_id,
             "description": f"{model_name} finding validator.",
             "system_prompt": _VALIDATOR_PROMPT,
             "skills": ["idor-validate"],
             "tools": _VALIDATOR_TOOLS},
        ],
    }


# --- Single-model graphs (scanner → validator) ---
# GPT OSS excluded from SAST — Bedrock request body limit too small
# for tool schemas + SAST prompt. Keep for DAST/recon where prompts
# are smaller.
SAST_SONNET_GRAPH = _make_graph(SONNET, "sonnet", "Sonnet 4.6")
SAST_HAIKU_GRAPH = _make_graph(HAIKU, "haiku", "Haiku 4.5")
SAST_NOVA2_GRAPH = _make_graph(NOVA2_LITE, "nova2", "Nova 2 Lite")

# --- Single-model swarms (scanner → validator) ---
SAST_SONNET_SWARM = _make_swarm(SONNET, "sonnet", "Sonnet 4.6")
SAST_HAIKU_SWARM = _make_swarm(HAIKU, "haiku", "Haiku 4.5")
SAST_NOVA2_SWARM = _make_swarm(NOVA2_LITE, "nova2", "Nova 2 Lite")

# Convenience lists for registration
SAST_SINGLE_GRAPHS: list[dict] = [
    SAST_SONNET_GRAPH, SAST_HAIKU_GRAPH,
    SAST_NOVA2_GRAPH,
]
SAST_SINGLE_SWARMS: list[dict] = [
    SAST_SONNET_SWARM, SAST_HAIKU_SWARM,
    SAST_NOVA2_SWARM,
]
