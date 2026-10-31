"""DAST IDOR — hybrid (graph-of-swarms) variant.

3 parallel 2-agent swarms (tester + verifier), each a different
model mix. Results converge on a prover agent.

Context variables: {{run_id}}, {{target_app}}, {{target_url}},
    {{sandbox_env_id}}, {{sast_run_id}}

Workflow detail (HTTP probes, mass assignment, evidence format,
AWS CLI prefix) lives in skills/idor-testing/SKILL.md,
skills/pentest-ops/SKILL.md, skills/sandbox-ops/SKILL.md —
loaded via the AgentSkills plugin. See bd python-factory-2xbi.
"""
from __future__ import annotations

from .models import SONNET, NOVA2_LITE, HAIKU, SCOUT, MAVERICK, GPT_OSS

_TESTER_PROMPT = (
    "You are an IDOR tester on a red team.\n"
    "Run ID: {{run_id}} | App: {{target_app}} | "
    "Target URL: {{target_url}} | Sandbox env: {{sandbox_env_id}}\n"
    "Agent ID: {{agent_id}}\n\n"
    "Use these skills (call the skills tool once for each):\n"
    "1. idor-testing — for the IDOR test workflow\n"
    "2. pentest-ops — for grounded evidence and tool use\n"
    "3. sandbox-ops — for HTTP exploitation and AWS CLI\n\n"
    "If a SAST run_id was provided ({{sast_run_id}}), use its "
    "CONFIRMED IDOR Findings as initial attack targets.\n"
    "Hand off via swarm/graph protocol when done."
)

_VERIFIER_PROMPT = (
    "You are an IDOR verifier on a red team.\n"
    "Run ID: {{run_id}} | App: {{target_app}} | "
    "Target URL: {{target_url}} | Sandbox env: {{sandbox_env_id}}\n"
    "Agent ID: {{agent_id}}\n\n"
    "Use these skills (call the skills tool once for each):\n"
    "1. idor-testing — for the IDOR test workflow\n"
    "2. pentest-ops — for grounded evidence and tool use\n"
    "3. sandbox-ops — for HTTP exploitation and AWS CLI\n\n"
    "When done, store learnings."
)

_PROVER_PROMPT = (
    "You are the IDOR prover on a red team.\n"
    "Run ID: {{run_id}} | App: {{target_app}} | "
    "Target URL: {{target_url}} | Sandbox env: {{sandbox_env_id}}\n"
    "Agent ID: prover\n\n"
    "Use these skills (call the skills tool once for each):\n"
    "1. idor-testing — for the IDOR test workflow\n"
    "2. pentest-ops — for grounded evidence and tool use\n"
    "3. sandbox-ops — for HTTP exploitation and AWS CLI\n\n"
    "Cross-reference findings across teams: 2/3+ agree → "
    "CONFIRMED; 1/3 → NEEDS_REVIEW. graph_add_entity "
    "type=IDORSummary.\n"
    "Do NOT hand off — you are last."
)

_TOOLS = ["think", "http_request"]
# bd:python-factory-2tgo1 — tester / verifier / prover prompts all
# explicitly name idor-testing, pentest-ops, sandbox-ops.
_IDOR_SKILLS = ["idor-testing", "pentest-ops", "sandbox-ops"]

# --- Team swarms ---

DAST_IDOR_HYBRID_TEAM_A: dict = {
    "id": "rt-idor-hybrid-team-a",
    "name": "IDOR Hybrid Team A (Sonnet + Haiku)",
    "description": "Sonnet tester + Haiku verifier.",
    "entry_point": "tester-a",
    "max_handoffs": 4, "max_iterations": 25,
    "agents": [
        {"id": "tester-a", "model": "",
         "description": "Sonnet IDOR tester.",
         "system_prompt": _TESTER_PROMPT, "tools": _TOOLS,
         "skills": list(_IDOR_SKILLS)},
        {"id": "verifier-a", "model": "",
         "description": "Haiku IDOR verifier.",
         "system_prompt": _VERIFIER_PROMPT, "tools": _TOOLS,
         "skills": list(_IDOR_SKILLS)},
    ],
}

DAST_IDOR_HYBRID_TEAM_B: dict = {
    "id": "rt-idor-hybrid-team-b",
    "name": "IDOR Hybrid Team B (GPT OSS + Scout)",
    "description": "GPT OSS tester + Scout verifier.",
    "entry_point": "tester-b",
    "max_handoffs": 4, "max_iterations": 25,
    "agents": [
        {"id": "tester-b", "model": "",
         "description": "GPT OSS IDOR tester.",
         "system_prompt": _TESTER_PROMPT, "tools": _TOOLS,
         "skills": list(_IDOR_SKILLS)},
        {"id": "verifier-b", "model": "",
         "description": "Scout IDOR verifier.",
         "system_prompt": _VERIFIER_PROMPT, "tools": _TOOLS,
         "skills": list(_IDOR_SKILLS)},
    ],
}

DAST_IDOR_HYBRID_TEAM_C: dict = {
    "id": "rt-idor-hybrid-team-c",
    "name": "IDOR Hybrid Team C (Nova2 Lite + Maverick)",
    "description": "Nova2 Lite tester + Maverick verifier.",
    "entry_point": "tester-c",
    "max_handoffs": 4, "max_iterations": 25,
    "agents": [
        {"id": "tester-c", "model": "",
         "description": "Nova2 Lite IDOR tester.",
         "system_prompt": _TESTER_PROMPT, "tools": _TOOLS,
         "skills": list(_IDOR_SKILLS)},
        {"id": "verifier-c", "model": "",
         "description": "Maverick IDOR verifier.",
         "system_prompt": _VERIFIER_PROMPT, "tools": _TOOLS,
         "skills": list(_IDOR_SKILLS)},
    ],
}

DAST_IDOR_HYBRID_SWARMS: list[dict] = [
    DAST_IDOR_HYBRID_TEAM_A,
    DAST_IDOR_HYBRID_TEAM_B,
    DAST_IDOR_HYBRID_TEAM_C,
]

DAST_IDOR_HYBRID_GRAPH: dict = {
    "id": "rt-scan-idor-hybrid",
    "name": "DAST IDOR (Hybrid Graph-of-Swarms)",
    "description": (
        "3 parallel 2-agent swarms (tester+verifier) → "
        "prover. Model diversity across teams."
    ),
    "required_bricks": ["graph", "security", "memory", "kb"],
    "context_vars": [
        "run_id", "target_app", "target_url",
        "sandbox_env_id", "sast_run_id",
    ],
    "entry_points": [
        "idor-team-a", "idor-team-b", "idor-team-c",
    ],
    "nodes": [
        {"id": "idor-team-a", "type": "swarm",
         "swarm_id": "rt-idor-hybrid-team-a",
         "description": "Sonnet tester + Haiku verifier"},
        {"id": "idor-team-b", "type": "swarm",
         "swarm_id": "rt-idor-hybrid-team-b",
         "description": "GPT OSS tester + Scout verifier"},
        {"id": "idor-team-c", "type": "swarm",
         "swarm_id": "rt-idor-hybrid-team-c",
         "description": "Nova2 Lite tester + Maverick verifier"},
        {"id": "prover", "type": "agent", "model": "",
         "description": "Cross-team validation + final verdict.",
         "system_prompt": _PROVER_PROMPT,
         "skills": list(_IDOR_SKILLS),
         "tools": _TOOLS},
    ],
    "edges": [
        {"source": "idor-team-a", "target": "prover"},
        {"source": "idor-team-b", "target": "prover"},
        {"source": "idor-team-c", "target": "prover"},
    ],
    "max_node_executions": 10,
    "execution_timeout": 900,
    "node_timeout": 300,
}
