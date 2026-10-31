"""DAST IDOR — sequential swarm variant (v2).

Discoverer (Haiku) → Tester-A (Sonnet) → Tester-B (GPT OSS)
→ Prover (Nova2 Lite). Each builds on prior HTTP test results.

Context variables: {{run_id}}, {{target_app}}, {{target_url}},
    {{sandbox_env_id}}, {{sast_run_id}}

Workflow detail (HTTP probes, mass assignment, evidence format,
AWS CLI prefix) lives in skills/idor-testing/SKILL.md,
skills/pentest-ops/SKILL.md, skills/sandbox-ops/SKILL.md —
loaded via the AgentSkills plugin. See bd python-factory-2xbi.
"""
from __future__ import annotations

from .models import SONNET, NOVA2_LITE, HAIKU, GPT_OSS

_DISCOVERER_PROMPT = (
    "You are an IDOR discoverer on a red team.\n"
    "Run ID: {{run_id}} | App: {{target_app}} | "
    "Target URL: {{target_url}} | Sandbox env: {{sandbox_env_id}}\n"
    "Agent ID: discoverer\n\n"
    "Use these skills (call the skills tool once for each):\n"
    "1. idor-testing — for the IDOR test workflow\n"
    "2. pentest-ops — for grounded evidence and tool use\n"
    "3. sandbox-ops — for HTTP exploitation and AWS CLI\n\n"
    "Hand off via swarm/graph protocol when done."
)

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

_PROVER_PROMPT = (
    "You are the IDOR prover on a red team.\n"
    "Run ID: {{run_id}} | App: {{target_app}} | "
    "Target URL: {{target_url}} | Sandbox env: {{sandbox_env_id}}\n"
    "Agent ID: prover\n\n"
    "Use these skills (call the skills tool once for each):\n"
    "1. idor-testing — for the IDOR test workflow\n"
    "2. pentest-ops — for grounded evidence and tool use\n"
    "3. sandbox-ops — for HTTP exploitation and AWS CLI\n\n"
    "Re-execute each ProvenExploit; verdict CONFIRMED / "
    "NEEDS_REVIEW / REJECTED; graph_add_entity type=IDORSummary.\n"
    "Do NOT hand off — you are last."
)

_TOOLS = ["think", "http_request"]
# bd:python-factory-2tgo1 — discoverer/tester/prover prompts all
# explicitly name idor-testing, pentest-ops, sandbox-ops.
_IDOR_SKILLS = ["idor-testing", "pentest-ops", "sandbox-ops"]

DAST_IDOR_SWARM: dict = {
    "id": "rt-scan-idor-swarm-v2",
    "name": "DAST IDOR (Sequential Swarm v2)",
    "description": (
        "Sequential: discoverer (Haiku) → tester-a (Sonnet) "
        "→ tester-b (GPT OSS) → prover (Nova2 Lite). "
        "Each builds on prior HTTP test results."
    ),
    "entry_point": "discoverer",
    "max_handoffs": 10,
    "max_iterations": 50,
    "agents": [
        {"id": "discoverer", "model": "",
         "description": "API endpoint discoverer.",
         "system_prompt": _DISCOVERER_PROMPT,
         "skills": list(_IDOR_SKILLS),
         "tools": _TOOLS},
        {"id": "tester-a", "model": "",
         "description": "IDOR tester (GET/PUT focus).",
         "system_prompt": _TESTER_PROMPT,
         "skills": list(_IDOR_SKILLS),
         "tools": _TOOLS},
        {"id": "tester-b", "model": "",
         "description": "IDOR tester (DELETE/POST focus).",
         "system_prompt": _TESTER_PROMPT,
         "skills": list(_IDOR_SKILLS),
         "tools": _TOOLS},
        {"id": "prover", "model": "",
         "description": "Final exploit validation.",
         "system_prompt": _PROVER_PROMPT,
         "skills": list(_IDOR_SKILLS),
         "tools": _TOOLS},
    ],
}
