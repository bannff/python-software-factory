"""SAST code scan — hybrid (graph-of-swarms) variant.

3 parallel 2-agent swarms (scanner + reviewer), each a different
model mix. Results converge on a consolidator agent, then a
validator agent challenges findings.

Context variables: {{vuln_class}}, {{target_app}}, {{run_id}},
    {{target_packages}}, {{sast_workspace}}

Workflow detail (phases, grounding, finding format) lives in
``skills/<vuln_class>-code-scan/SKILL.md``. Per-agent prompts here
are intentionally thin. Consolidator/validator stay inline (Tier D —
graph-level coordination, no specialist skill counterpart).
See bd python-factory-2xbi.
"""
from __future__ import annotations

from .models import SONNET, NOVA2_LITE, HAIKU, SCOUT, MAVERICK, GPT_OSS
from .vuln_class_config import VULN_CLASS_CONFIG

_VULN_REF = "\n".join(
    f"  {vc}: {cfg['cwe']} ({cfg['owasp_ref']})"
    for vc, cfg in VULN_CLASS_CONFIG.items()
)

_SCANNER_PROMPT = (
    "You are a SAST scanner in a 2-agent swarm team.\n"
    "Run ID: {{run_id}} | App: {{target_app}} | "
    "Vuln class: {{vuln_class}} | Workspace: {{sast_workspace}}\n\n"
    "Use the `{{vuln_class}}-code-scan` skill for the workflow. "
    "Activate it now via the skills tool, then follow its phases.\n"
    "When done, hand off via swarm protocol to the reviewer.\n\n"
    "CWE REF:\n" + _VULN_REF
)

_REVIEWER_PROMPT = (
    "You are a code reviewer in a 2-agent swarm team — you build "
    "on the scanner's findings.\n"
    "Run ID: {{run_id}} | App: {{target_app}} | "
    "Vuln class: {{vuln_class}} | Workspace: {{sast_workspace}}\n\n"
    "Use the `{{vuln_class}}-code-scan` skill for the workflow. "
    "Activate it now via the skills tool, then follow its phases.\n"
    "Use graph_find_entities(entity_type='SuspectedVuln', "
    "properties={'run_id': '{{run_id}}'}) to load prior findings, "
    "file_read each cited file, find vulns the scanner missed, "
    "store new findings with agent_id='reviewer'. Do NOT hand off — "
    "you are last in this team.\n\n"
    "CWE REF:\n" + _VULN_REF
)

_SCAN_TOOLS = ["think", "file_read",
               "editor", "shell"]
_REVIEW_TOOLS = ["think", "file_read"]

# --- Team swarms (registered separately for graph refs) ---
_TEAMS = [
    ("a", "rt-sast-hybrid-team-a", "GPT OSS + Haiku",
     GPT_OSS, HAIKU),
    ("b", "rt-sast-hybrid-team-b", "Sonnet + Scout",
     SONNET, SCOUT),
    ("c", "rt-sast-hybrid-team-c", "Nova2 Lite + Maverick",
     NOVA2_LITE, MAVERICK),
]

SAST_HYBRID_SWARMS: list[dict] = []
for _sfx, _sid, _desc, _scan_m, _rev_m in _TEAMS:
    _swarm: dict = {
        "id": _sid,
        "name": f"SAST Hybrid Team {_sfx.upper()} ({_desc})",
        "description": f"{_desc.split(' + ')[0]} scanner + {_desc.split(' + ')[1]} reviewer.",
        "entry_point": f"scanner-{_sfx}",
        "max_handoffs": 4, "max_iterations": 15,
        "agents": [
            # bd:python-factory-2tgo1 — scanner+reviewer prompts
            # both reference the `{{vuln_class}}-code-scan` skill;
            # only `idor-code-scan` exists in skills/ today.
            {"id": f"scanner-{_sfx}", "model": _scan_m,
             "description": f"{_desc.split(' + ')[0]} SAST scanner.",
             "system_prompt": _SCANNER_PROMPT, "tools": _SCAN_TOOLS,
             "skills": ["idor-code-scan"]},
            {"id": f"reviewer-{_sfx}", "model": _rev_m,
             "description": f"{_desc.split(' + ')[1]} code reviewer.",
             "system_prompt": _REVIEWER_PROMPT, "tools": _REVIEW_TOOLS,
             "skills": ["idor-code-scan"]},
        ],
    }
    SAST_HYBRID_SWARMS.append(_swarm)

# --- Consolidator + Validator (Tier D — graph-level coordination, no skill) ---

_CONSOLIDATOR_PROMPT = (
    "You are a finding consolidator for a SAST code scan.\n"
    "RUN ID: {{run_id}} | APP: {{target_app}} | "
    "VULN CLASS: {{vuln_class}}\n\n"
    "STEP 0 — memory_retrieve('{{vuln_class}} consolidation',\n"
    "  user_id='kiro-agent', limit=5)\n\n"
    "3 teams scanned code independently. Your job:\n"
    "1) graph_find_entities(entity_type='SuspectedVuln',\n"
    "   properties={'run_id': '{{run_id}}'})\n"
    "2) Group by (file, function). Count distinct agent_id.\n"
    "3) 2/3+ teams → CONFIRMED. 1/3 → NEEDS_REVIEW.\n"
    "4) security.classify_confidence for each\n"
    "5) Deduplicate into Finding entities with verdict\n"
    "6) For each consolidated row, write a canonical Finding so F1\n"
    "   scoring picks it up:\n"
    "   graph_add_entity(entity_type='Finding',\n"
    "     entity_id='finding-{{run_id}}-<n>',\n"
    "     properties={'run_id': '{{run_id}}', 'app': '{{target_app}}',\n"
    "                 'vuln_class': '{{vuln_class}}',\n"
    "                 'verdict': '<CONFIRMED|NEEDS_REVIEW>',\n"
    "                 'cwe': '<CWE id>', 'severity': '...',\n"
    "                 'file': '...', 'function': '...',\n"
    "                 'line_start': <int>, 'line_end': <int>})\n"
    "7) memory_store(user_id='kiro-agent', memory_type="
    "'long_term', category='fact')\n"
)

_VALIDATOR_PROMPT = (
    "You are a finding validator for a SAST code scan.\n"
    "RUN ID: {{run_id}} | APP: {{target_app}} | "
    "VULN CLASS: {{vuln_class}} | Workspace: {{sast_workspace}}\n\n"
    "STEP 0 — memory_retrieve('{{vuln_class}} validation',\n"
    "  user_id='kiro-agent', limit=5)\n\n"
    "1) graph_get_findings_for_run(run_id='{{run_id}}')\n"
    "2) file_read each cited file — verify snippet\n"
    "3) Check for mitigating controls\n"
    "4) think(cycle_count=3) — argue why NOT vulnerable\n"
    "5) Update verdict: CONFIRMED / NEEDS_REVIEW / REJECTED\n"
    "6) security_classify_finding for each\n"
    "7) memory_store(user_id='kiro-agent', memory_type="
    "'long_term', category='fact')\n"
)

SAST_HYBRID_GRAPH: dict = {
    "id": "rt-sast-scan-hybrid",
    "name": "SAST Code Scan (Hybrid Graph-of-Swarms)",
    "description": (
        "3 parallel 2-agent swarms (scanner+reviewer) → "
        "consolidator → validator. Model diversity across teams."
    ),
    "required_bricks": ["graph", "security", "memory", "kb"],
    "context_vars": [
        "vuln_class", "target_app", "run_id",
        "target_packages", "sast_workspace",
    ],
    "entry_points": [
        "scan-team-a", "scan-team-b", "scan-team-c",
    ],
    "nodes": [
        {"id": "scan-team-a", "type": "swarm",
         "swarm_id": "rt-sast-hybrid-team-a",
         "description": "GPT OSS scanner + Haiku reviewer"},
        {"id": "scan-team-b", "type": "swarm",
         "swarm_id": "rt-sast-hybrid-team-b",
         "description": "Sonnet scanner + Scout reviewer"},
        {"id": "scan-team-c", "type": "swarm",
         "swarm_id": "rt-sast-hybrid-team-c",
         "description": "Nova2 Lite scanner + Maverick reviewer"},
        # bd:python-factory-2tgo1 — Tier-D coordinator nodes have no
        # specialist skill (prompts are fully inline).
        {"id": "consolidator", "type": "agent", "model": "",
         "description": "Merges findings via 2/3 voting.",
         "system_prompt": _CONSOLIDATOR_PROMPT,
         "skills": [],
         "tools": ["think"]},
        {"id": "validator", "type": "agent", "model": "",
         "description": "Adversarial challenge of findings.",
         "system_prompt": _VALIDATOR_PROMPT,
         "skills": [],
         "tools": ["think", "file_read"],
         "context": {"agent_id": "validator"}},
    ],
    "edges": [
        {"source": "scan-team-a", "target": "consolidator"},
        {"source": "scan-team-b", "target": "consolidator"},
        {"source": "scan-team-c", "target": "consolidator"},
        {"source": "consolidator", "target": "validator"},
    ],
    "max_node_executions": 3,
    "execution_timeout": 5400,
    "node_timeout": 1800,
}
