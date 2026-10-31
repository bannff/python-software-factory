"""Red team IDOR graph — parallel agents per vuln class.

3 agents run in parallel (GPT OSS, Sonnet, GLM 5), each
independently testing IDOR vectors. Evals/metrics/rewards run
automatically via event subscriptions — NOT wired into this graph.

Context variables: {{run_id}}, {{target_app}}, {{sandbox_env_id}}

Workflow detail (HTTP probes, mass assignment, evidence format)
lives in skills/idor-testing/SKILL.md, skills/pentest-ops/SKILL.md,
skills/sandbox-ops/SKILL.md — loaded via the AgentSkills plugin.
See bd python-factory-2xbi.
"""
from __future__ import annotations

from .models import SONNET, GLM5, GPT_OSS

_IDOR_PROMPT = (
    "You are an IDOR specialist on a red team.\n"
    "Run ID: {{run_id}} | App: {{target_app}} | "
    "Target URL: {{target_url}} | Sandbox env: {{sandbox_env_id}}\n"
    "OWASP: WSTG-ATHZ-04 (CWE-639).\n\n"
    "Use these skills (call the skills tool once for each):\n"
    "1. idor-testing — for the IDOR test workflow\n"
    "2. pentest-ops — for grounded evidence and tool use\n"
    "3. sandbox-ops — for LocalStack and HTTP exploitation\n\n"
    "If a SAST run_id was provided ({{sast_run_id}}), first query "
    "graph for CONFIRMED IDOR Findings from that run and use their "
    "recommended_test as your initial attack targets.\n"
    "Test the TARGET URL via HTTP (curl), NOT raw DynamoDB — the "
    "target is a REST API."
)

# --- Graph config (domain-specific only) ---

# bd:python-factory-2tgo1 — IDOR specialist prompt explicitly names
# 3 skills: idor-testing, pentest-ops, sandbox-ops.
_IDOR_SKILLS = ["idor-testing", "pentest-ops", "sandbox-ops"]

SCAN_IDOR_GRAPH: dict = {
    "id": "rt-scan-idor",
    "name": "Scan IDOR (Parallel Agents)",
    "description": (
        "3 models test IDOR in parallel. Post-workflow "
        "eval/metrics/rewards handled by event subscriptions."
    ),
    "entry_points": ["gptoss-idor", "sonnet-idor", "glm5-idor"],
    "nodes": [
        {"id": "gptoss-idor", "type": "agent", "model": "",
         "description": "GPT OSS IDOR tester.",
         "system_prompt": _IDOR_PROMPT,
         "skills": list(_IDOR_SKILLS),
         "tools": ["think",
                    "http_request"]},
        {"id": "sonnet-idor", "type": "agent", "model": "",
         "description": "Sonnet IDOR tester.",
         "system_prompt": _IDOR_PROMPT,
         "skills": list(_IDOR_SKILLS),
         "tools": ["think",
                    "http_request"]},
        {"id": "glm5-idor", "type": "agent",
         "model": "",
         "description": "GLM 5 IDOR tester.",
         "system_prompt": _IDOR_PROMPT,
         "skills": list(_IDOR_SKILLS),
         "tools": ["think",
                    "http_request"]},
    ],
    "edges": [],  # All 3 run in parallel, no dependencies
    "max_node_executions": 10,
    "execution_timeout": 900,
    "node_timeout": 300,
}

# Legacy swarm (deprecated)
SCAN_IDOR_SWARM: dict = {
    "id": "rt-scan-idor-swarm",
    "name": "Scan IDOR (Legacy Swarm)",
    "description": "DEPRECATED — use rt-scan-idor graph.",
    "entry_point": "idor-lead",
    "max_handoffs": 8, "max_iterations": 50,
    "agents": [
        {"id": "idor-lead", "model": "",
         "description": "Lead IDOR tester.",
         "system_prompt": _IDOR_PROMPT,
         "skills": list(_IDOR_SKILLS),
         "tools": ["think",
                    "http_request"]},
    ],
}
