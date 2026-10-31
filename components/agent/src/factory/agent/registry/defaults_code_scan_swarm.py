"""SAST code scan — sequential swarm variant.

Agents hand off sequentially, each building on prior findings.
Scanner (Sonnet) → Reviewer (GPT OSS) → Consolidator (Nova2 Lite)
→ Validator (Sonnet).

Context variables: {{vuln_class}}, {{target_app}}, {{run_id}},
    {{target_packages}}, {{sast_workspace}}

Workflow detail (phases, grounding rules, finding format) lives in
``skills/<vuln_class>-code-scan/SKILL.md``. Per-agent prompts here
are intentionally thin. Consolidator/validator stay inline (Tier D —
graph-level coordination). See bd python-factory-2xbi.
"""
from __future__ import annotations

from .models import SONNET, NOVA2_LITE, GPT_OSS
from .vuln_class_config import VULN_CLASS_CONFIG

_VULN_REF = "\n".join(
    f"  {vc}: {cfg['cwe']} ({cfg['owasp_ref']})"
    for vc, cfg in VULN_CLASS_CONFIG.items()
)

_SCANNER_PROMPT = (
    "You are the lead SAST scanner in a sequential swarm team.\n"
    "Run ID: {{run_id}} | App: {{target_app}} | "
    "Vuln class: {{vuln_class}} | Workspace: {{sast_workspace}}\n\n"
    "Use the `{{vuln_class}}-code-scan` skill for the workflow. "
    "Activate it now via the skills tool, then follow its phases.\n"
    "When done, hand off via swarm protocol to the reviewer.\n\n"
    "CWE REF:\n" + _VULN_REF
)

_REVIEWER_PROMPT = (
    "You are a code reviewer building on the scanner's work.\n"
    "Run ID: {{run_id}} | App: {{target_app}} | "
    "Vuln class: {{vuln_class}} | Workspace: {{sast_workspace}}\n\n"
    "Use the `{{vuln_class}}-code-scan` skill for the workflow. "
    "Activate it now via the skills tool, then follow its phases.\n"
    "Use graph_find_entities(entity_type='SuspectedVuln', "
    "properties={'run_id': '{{run_id}}'}) to load prior findings, "
    "file_read each cited file, find vulns the scanner missed, "
    "store new findings with agent_id='reviewer'. Hand off to "
    "consolidator.\n"
)

# Tier D — graph-level coordination, no specialist skill counterpart.

_CONSOLIDATOR_PROMPT = (
    "You are the consolidator. Merge all findings.\n"
    "RUN ID: {{run_id}} | APP: {{target_app}} | "
    "VULN CLASS: {{vuln_class}}\n\n"
    "STEP 0 — memory_retrieve('{{vuln_class}} consolidation',\n"
    "  user_id='kiro-agent', limit=5)\n\n"
    "1) graph_find_entities(entity_type='SuspectedVuln',\n"
    "   properties={'run_id': '{{run_id}}'})\n"
    "2) Deduplicate by (file, function)\n"
    "3) Both agents agree → CONFIRMED; one only → NEEDS_REVIEW\n"
    "4) security.classify_confidence for each\n"
    "5) Store as Finding with verdict\n"
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
    "7) Hand off to validator.\n"
)

_VALIDATOR_PROMPT = (
    "You are the validator. Challenge each finding.\n"
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
    "7) memory_store(user_id='kiro-agent', memory_type='long_term',"
    " category='fact')\n"
    "8) Do NOT hand off — you are last.\n"
)

SAST_SCAN_SWARM: dict = {
    "id": "rt-sast-scan-swarm",
    "name": "SAST Code Scan (Sequential Swarm)",
    "description": (
        "Sequential handoff: scanner (Sonnet) → reviewer "
        "(GPT OSS) → consolidator (Nova2 Lite) → validator "
        "(Sonnet). Each builds on prior findings via graph."
    ),
    "entry_point": "scanner",
    "max_handoffs": 10,
    "max_iterations": 30,
    "agents": [
        # bd:python-factory-2tgo1 — per-agent skills mirror the
        # prompts. Scanner+reviewer ref `<vuln_class>-code-scan`;
        # validator refs no skill in the swarm variant (prompt is
        # fully inline). Tier-D consolidator: skills=[].
        {"id": "scanner", "model": "",
         "description": "Lead SAST scanner.",
         "system_prompt": _SCANNER_PROMPT,
         "skills": ["idor-code-scan"],
         "tools": ["think", "file_read",
                    "editor", "shell"]},
        {"id": "reviewer", "model": "",
         "description": "Reviews and extends scanner findings.",
         "system_prompt": _REVIEWER_PROMPT,
         "skills": ["idor-code-scan"],
         "tools": ["think", "file_read"]},
        {"id": "consolidator", "model": "",
         "description": "Merges and deduplicates findings.",
         "system_prompt": _CONSOLIDATOR_PROMPT,
         "skills": [],
         "tools": ["think"]},
        {"id": "validator", "model": "",
         "description": "Adversarial validation of findings.",
         "system_prompt": _VALIDATOR_PROMPT,
         "skills": [],
         "tools": ["think", "file_read"]},
    ],
}
