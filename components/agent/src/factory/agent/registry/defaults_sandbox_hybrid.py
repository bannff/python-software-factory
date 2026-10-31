"""Sandbox setup — hybrid (graph-of-swarms) variant.

2 parallel 2-agent swarms (creator + checker) → summary agent.

Context variables: {{run_id}}, {{target_app}}

Workflow detail (sandbox CLI patterns, AWS CLI prefix, mock
config, validation commands) lives in skills/sandbox-ops/SKILL.md — loaded via the
AgentSkills plugin. See bd python-factory-2xbi.
"""
from __future__ import annotations

from .models import HAIKU, SONNET, SCOUT, GPT_OSS

_CREATOR_PROMPT = (
    "You are a sandbox creator in a 2-agent team.\n"
    "Run ID: {{run_id}} | App: {{target_app}}\n"
    "Agent ID: {{agent_id}}\n\n"
    "Use these skills (call the skills tool once for each):\n"
    "1. sandbox-ops — for sandbox + AWS CLI patterns\n"
    "When done, hand off via swarm/graph protocol."
)

_CHECKER_PROMPT = (
    "You are a sandbox checker in a 2-agent team.\n"
    "Run ID: {{run_id}} | App: {{target_app}}\n"
    "Agent ID: {{agent_id}}\n\n"
    "Use these skills (call the skills tool once for each):\n"
    "1. sandbox-ops — for sandbox + AWS CLI patterns\n"
    "When done, store learnings."
)

_SUMMARY_PROMPT = (
    "You are the sandbox summary agent.\n"
    "Run ID: {{run_id}} | App: {{target_app}}\n"
    "Agent ID: summary\n\n"
    "Use the sandbox-ops skill. Activate it via the skills tool, "
    "then follow its phases.\n"
    "Cross-reference: both teams agree → confirmed; "
    "graph_add_entity type=SandboxSummary with counts."
)

# --- Team swarms ---

SANDBOX_HYBRID_TEAM_A: dict = {
    "id": "rt-sandbox-hybrid-team-a",
    "name": "Sandbox Hybrid Team A (Haiku + GPT OSS)",
    "description": "Haiku creator + GPT OSS checker.",
    "entry_point": "creator-a",
    "max_handoffs": 4, "max_iterations": 15,
    "agents": [
        # bd:python-factory-2tgo1 — both prompts name sandbox-ops.
        {"id": "creator-a", "model": "",
         "description": "Haiku sandbox creator.",
         "system_prompt": _CREATOR_PROMPT, "tools": [],
         "skills": ["sandbox-ops"]},
        {"id": "checker-a", "model": "",
         "description": "GPT OSS sandbox checker.",
         "system_prompt": _CHECKER_PROMPT, "tools": [],
         "skills": ["sandbox-ops"]},
    ],
}

SANDBOX_HYBRID_TEAM_B: dict = {
    "id": "rt-sandbox-hybrid-team-b",
    "name": "Sandbox Hybrid Team B (Scout + Sonnet)",
    "description": "Scout creator + Sonnet checker.",
    "entry_point": "creator-b",
    "max_handoffs": 4, "max_iterations": 15,
    "agents": [
        {"id": "creator-b", "model": "",
         "description": "Scout sandbox creator.",
         "system_prompt": _CREATOR_PROMPT, "tools": [],
         "skills": ["sandbox-ops"]},
        {"id": "checker-b", "model": "",
         "description": "Sonnet sandbox checker.",
         "system_prompt": _CHECKER_PROMPT, "tools": [],
         "skills": ["sandbox-ops"]},
    ],
}

SANDBOX_HYBRID_SWARMS: list[dict] = [
    SANDBOX_HYBRID_TEAM_A, SANDBOX_HYBRID_TEAM_B,
]

SANDBOX_HYBRID_GRAPH: dict = {
    "id": "rt-sandbox-setup-hybrid",
    "name": "Sandbox Setup (Hybrid Graph-of-Swarms)",
    "description": (
        "2 parallel 2-agent swarms (creator+checker) "
        "→ Sonnet summary agent."
    ),
    "required_bricks": ["graph", "security", "memory", "kb"],
    "context_vars": ["run_id", "target_app"],
    "entry_points": ["sandbox-team-a", "sandbox-team-b"],
    "nodes": [
        {"id": "sandbox-team-a", "type": "swarm",
         "swarm_id": "rt-sandbox-hybrid-team-a",
         "description": "Haiku creator + GPT OSS checker"},
        {"id": "sandbox-team-b", "type": "swarm",
         "swarm_id": "rt-sandbox-hybrid-team-b",
         "description": "Scout creator + Sonnet checker"},
        {"id": "summary", "type": "agent", "model": "",
         "description": "Summarizes sandbox state.",
         "system_prompt": _SUMMARY_PROMPT,
         "skills": ["sandbox-ops"],
         "tools": ["think"]},
    ],
    "edges": [
        {"source": "sandbox-team-a", "target": "summary"},
        {"source": "sandbox-team-b", "target": "summary"},
    ],
    "max_node_executions": 3,
    "execution_timeout": 1800,
    "node_timeout": 600,
}
