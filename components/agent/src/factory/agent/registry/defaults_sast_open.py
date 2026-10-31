"""Open-scope SAST workflow — agent chains attacks across 9 vuln classes.

Sibling of ``defaults_code_scan.py`` (sast-targeted, bd-a4h7) but
broader: NOT scoped to a single vuln_class. Same 6-task DAG (3
parallel scanners → hierarchy-analyzer → consolidator → validator)
but with an open-scope playbook that asks the agent to reason across
IDOR / SQLi / XSS / SSRF / CSRF / Path-Traversal / Cmd-Injection /
Deserialization / Mass-Assignment AND to compound findings into
attack chains.

Per meta-architect verdict (memory ``f4d01009``) and strands-expert
verdict (memory ``ffa4b8ee``):
- Skill activation = numbered-list of ``pentest-ops``,
  ``sast-open-scan``, ``swarm-collaboration``. NO IDOR-wedge skills
  (would prime the model toward IDOR via 150 LOC of class-specific
  phases).
- NO ``{{vuln_class}}`` template anywhere — open variant has no
  per-call class input. Factory is a pure constant.
- Same models as targeted (GPT_OSS / SONNET / GLM5) — diversity
  surfaces different chains across reasoning styles.
- NO embedded eval-scorer task — eval/metrics/rewards land via
  event subscriptions on ``graph.completed`` (auto-eval-workflow,
  auto-rewards-workflow, auto-metrics-workflow).
- Bare-name tools (``workflow.py`` L329-336 filter contract).
- ``factory="sast_open"`` string registry key per Option A
  (registrations stay pure data, mem ``33b12ebb``).

Workflow detail (phases, grounding rules, 9 CWE classes, attack
chaining heuristics) lives in
``skills/sast-open-scan/SKILL.md`` — loaded via the AgentSkills
plugin (progressive disclosure). Per-agent prompts here are thin —
role + context + skill activation + cross-class chaining note.
"""
from __future__ import annotations

from factory.agent.runtime.registry_contracts import WorkflowConfig
from .models import GLM5, GPT_OSS, SONNET

# --- SAST-open scanner prompt (thin — workflow lives in SKILL.md) ----
_SAST_OPEN_PROMPT = (
    "You are an open-scope SAST code scanner on a security red team.\n"
    "Run ID: {{run_id}} | App: {{target_app}} | "
    "Workspace: {{sast_workspace}}\n"
    "Target packages: {{target_packages}}\n\n"
    "You are NOT scoped to a single vulnerability class. Scan source "
    "for ANY exploitable weakness across IDOR, SQLi, XSS, SSRF, CSRF, "
    "Path Traversal, Command Injection, Deserialization, and Mass "
    "Assignment. Critically, reason about how findings COMPOUND into "
    "attack chains — e.g. missing authz + path traversal, or IDOR + "
    "SQLi reaching the same DAO sink — and call that out explicitly.\n\n"
    "Use these skills (call the skills tool once for each):\n"
    "1. pentest-ops — for grounded evidence and tool use\n"
    "2. sast-open-scan — for the open-scope SAST playbook\n"
    "3. swarm-collaboration — for handoff protocol\n\n"
    "Tag every finding with its vuln_class and CWE id. When done, "
    "summarise into the task result."
)

# --- Hierarchy analyzer prompt (Tier D — coordination, no skill) -----
_HIERARCHY_PROMPT = (
    "You are a hierarchy analyzer for an open-scope SAST scan.\n"
    "Run ID: {{run_id}} | App: {{target_app}}\n\n"
    "3 scanners produced cross-class findings. Your job:\n"
    "1) Read scanner findings from the dependency results.\n"
    "2) Group by (resource, HTTP method) AND by data-flow chain.\n"
    "3) Flag INCONSISTENCIES across endpoints touching the same "
    "resource (e.g. authz applied on GET but missing on PUT).\n"
    "4) Surface CHAIN candidates where two findings on different "
    "vuln classes touch the same code path.\n"
    "5) Reason for ~2 cycles, validate each inconsistency / chain.\n"
    "6) Emit a structured hierarchy + chain report as the task result."
)

# --- Consolidator prompt (Tier D — coordination, no skill) -----------
_CONSOLIDATOR_PROMPT = (
    "You are a finding consolidator for an open-scope SAST scan.\n"
    "Run ID: {{run_id}} | App: {{target_app}}\n\n"
    "3 scanners scanned code independently across 9 vuln classes. "
    "Your job:\n"
    "1) Read each scanner's findings from the dependency results.\n"
    "2) Group by (file, function, vuln_class). Count distinct "
    "agent_id per (file, function, vuln_class) tuple.\n"
    "3) 2/3+ agents agree -> CONFIRMED. 1/3 -> NEEDS_REVIEW.\n"
    "4) Use the hierarchy-analyzer's chain report to BOOST confidence "
    "for findings that participate in cross-class attack chains.\n"
    "5) Deduplicate into Finding records carrying vuln_class + verdict + "
    "reason + chain_membership.\n"
    "6) Emit a structured consensus summary as the task result."
)

# --- Validator prompt (open-scope, uses sast-open-scan skill) --------
_VALIDATOR_PROMPT = (
    "You are an open-scope SAST finding validator on a security red "
    "team.\n"
    "Run ID: {{run_id}} | App: {{target_app}} | "
    "Workspace: {{sast_workspace}}\n\n"
    "Use these skills (call the skills tool once for each):\n"
    "1. pentest-ops — for grounded evidence and tool use\n"
    "2. sast-open-scan — for the open-scope SAST playbook\n"
    "3. swarm-collaboration — for handoff protocol\n\n"
    "Adversarially challenge each CONFIRMED finding from the "
    "consolidator: re-read the cited file/function, validate the "
    "data-flow claim, and downgrade to NEEDS_REVIEW or REJECTED if "
    "the evidence is thin. Pay special attention to chained findings "
    "— a weak link breaks the chain.\n"
    "When done, store the validation summary."
)

# --- Bare-name tool sets (workflow.py L329-336 filter contract) ------
_SCAN_TOOLS = ["think", "file_read", "editor", "shell", "http_request"]
_HIERARCHY_TOOLS = ["think"]
_CONSOLIDATOR_TOOLS = ["think"]
_VALIDATOR_TOOLS = ["think", "file_read", "graph_add_entity",
                    "graph_add_relationship", "graph_get_findings_for_run"]


def _task(
    task_id: str, prompt: str, tools: list[str], model: str,
    deps: list[str], prio: int, skills: list[str] | None = None,
) -> dict:
    """Build one Workflow task dict. Pure — no rendering.

    bd:python-factory-2tgo1 — ``skills`` is the per-task AgentSkills
    attach list. Empty for Tier-D coordination tasks (hierarchy-
    analyzer, consolidator) that have no skill counterpart.
    """
    return {
        "task_id": task_id, "description": prompt,
        "system_prompt": prompt, "tools": list(tools),
        "skills": list(skills or []),
        "model_provider": "bedrock",
        "model_settings": {"model_id": model},
        "dependencies": list(deps),
        "priority": prio, "timeout": 1800,
    }


def build_sast_open_tasks() -> list[dict]:
    """Render the 6-task open-scope SAST DAG.

    Pure-constant — open SAST takes no per-call inputs (no
    ``vuln_class`` since the variant is cross-class). Template
    markers (``{{run_id}}``, ``{{target_app}}``, ``{{sast_workspace}}``,
    ``{{target_packages}}``) are resolved by ``WorkflowExecutor`` at
    create time.  Hypothesis-property tested in
    ``test_factories_sast_open.py`` (50 examples).
    """
    # bd:python-factory-2tgo1 — scanner+validator prompts both name
    # pentest-ops, sast-open-scan, swarm-collaboration.
    scan_skills = ["pentest-ops", "sast-open-scan", "swarm-collaboration"]
    return [
        _task("gptoss-sast", _SAST_OPEN_PROMPT, _SCAN_TOOLS, GPT_OSS, [], 5,
              skills=scan_skills),
        _task("sonnet-sast", _SAST_OPEN_PROMPT, _SCAN_TOOLS, SONNET, [], 5,
              skills=scan_skills),
        _task("glm5-sast", _SAST_OPEN_PROMPT, _SCAN_TOOLS, GLM5, [], 5,
              skills=scan_skills),
        _task("hierarchy-analyzer", _HIERARCHY_PROMPT, _HIERARCHY_TOOLS,
              SONNET, ["gptoss-sast", "sonnet-sast", "glm5-sast"], 4,
              skills=[]),
        _task("consolidator", _CONSOLIDATOR_PROMPT, _CONSOLIDATOR_TOOLS,
              SONNET, ["hierarchy-analyzer"], 3, skills=[]),
        _task("validator", _VALIDATOR_PROMPT, _VALIDATOR_TOOLS, GLM5,
              ["consolidator"], 2, skills=scan_skills),
    ]


# --- Workflow registration --------------------------------------------

SAST_OPEN_REGISTRATION = WorkflowConfig(
    id="sast",
    kind="workflow",
    factory="sast_open",
    name="SAST Open Scan (Workflow)",
    description=(
        "Open-scope SAST for {{target_app}}: 3 models scan source "
        "code in parallel (GPT OSS, Sonnet, GLM 5). Broader scope, "
        "agent chains exploits across 9 vuln classes "
        "(IDOR/SQLi/XSS/SSRF/CSRF/Path-Traversal/Cmd-Injection/"
        "Deserialization/Mass-Assignment). Hierarchy-analyzer "
        "surfaces chain candidates; consolidator merges via 2/3 "
        "voting; validator (GLM 5) adversarially challenges."
    ),
    required_bricks=["graph", "security", "memory", "kb"],
    context_vars=[
        "target_app", "run_id", "target_packages", "sast_workspace",
    ],
    execution_timeout=5400,
    node_timeout=1800,
)

# Back-compat export — defaults.py imports SAST_OPEN_GRAPHS as a
# 1-element list of WorkflowConfig (matches RECON_GRAPHS / SANDBOX_GRAPHS
# shape so the GRAPHS_TYPED concatenation stays uniform).
SAST_OPEN_GRAPHS: list = [SAST_OPEN_REGISTRATION]
