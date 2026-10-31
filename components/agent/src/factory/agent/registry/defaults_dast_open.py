"""Open-scope DAST workflow — agent probes 9 vuln classes via runtime.

Sibling of ``defaults_redteam_idor_swarm.py`` (rt-scan-idor) but
broader: NOT scoped to a single vuln_class. Flat 3-parallel
topology — 3 testers run independently with no DAG dependencies
(matches Strands Workflow constraint: no conditional fan-out, so
broader exploration is owned by the prompt, not the topology).

Per meta-architect verdict (memory ``f4d01009``) and strands-expert
verdict (memory ``ffa4b8ee``):
- Skill activation = numbered-list of ``pentest-ops``,
  ``sandbox-ops``, ``dast-open-scan``, ``swarm-collaboration``. NO
  IDOR-wedge skills (would prime the model toward IDOR).
- NO ``{{vuln_class}}`` template — open variant has no per-call
  class input. Factory is a pure constant.
- Same diversity (GPT_OSS / SONNET / GLM5) as targeted — different
  reasoning styles surface different runtime chains.
- Bare-name tools (``workflow.py`` L329-336 filter contract).
- ``factory="dast_open"`` string registry key (Option A).

Workflow detail (HTTP probing, sandbox CLI, AWS CLI prefix, 9 CWE
classes, attack chaining heuristics) lives in
``skills/dast-open-scan/SKILL.md`` — loaded via the AgentSkills
plugin. Per-agent prompts here are thin.
"""
from __future__ import annotations

from factory.agent.runtime.registry_contracts import WorkflowConfig
from .models import GLM5, GPT_OSS, SONNET

# --- DAST-open tester prompt (thin — workflow lives in SKILL.md) -----
_DAST_OPEN_PROMPT = (
    "You are an open-scope DAST runtime tester on a security red team.\n"
    "Run ID: {{run_id}} | App: {{target_app}} | "
    "Target URL: {{target_url}} | Sandbox env: {{sandbox_env_id}}\n\n"
    "You are NOT scoped to a single vulnerability class. Probe the "
    "live target for ANY exploitable weakness across IDOR, SQLi, XSS, "
    "SSRF, CSRF, Path Traversal, Command Injection, Auth Bypass, "
    "and Mass Assignment. Critically, COMPOUND probes — e.g. an IDOR "
    "that returns SQL error strings, or an SSRF that reaches an "
    "internal admin endpoint — and call those chains out explicitly.\n\n"
    "Use these skills (call the skills tool once for each):\n"
    "1. pentest-ops — for grounded evidence and tool use\n"
    "2. sandbox-ops — for HTTP probing, sandbox CLI, AWS CLI prefix\n"
    "3. dast-open-scan — for the open-scope DAST playbook\n"
    "4. swarm-collaboration — for handoff protocol\n\n"
    "If a SAST run_id was provided ({{sast_run_id}}), call "
    "graph_get_findings_for_run(run_id='{{sast_run_id}}') — the "
    "typed tool joins CWE/OCSF taxonomy and works on both networkx "
    "and Neo4j — and use the CONFIRMED rows as initial probe "
    "targets.\n"
    "Tag every finding with its vuln_class and CWE id; include the "
    "exact request/response pair as evidence. When done, summarise "
    "into the task result."
)

# --- Bare-name tool set (workflow.py L329-336 filter contract) -------
_DAST_TOOLS = ["think", "http_request", "sandbox_execute",
               "graph_add_entity", "graph_add_relationship",
               "graph_find_entities", "graph_get_findings_for_run",
               "memory_store", "memory_retrieve"]


def _task(
    task_id: str, prompt: str, tools: list[str], model: str,
    deps: list[str], prio: int,
) -> dict:
    """Build one Workflow task dict. Pure — no rendering.

    bd:python-factory-2tgo1 — open DAST tester prompt names skills
    explicitly: ``pentest-ops``, ``sandbox-ops``, ``dast-open-scan``,
    ``swarm-collaboration``. Populated on every task so AgentSkills
    scopes loads to those four.
    """
    return {
        "task_id": task_id,
        "description": prompt,
        "system_prompt": prompt,
        "tools": list(tools),
        "skills": ["pentest-ops", "sandbox-ops", "dast-open-scan",
                   "swarm-collaboration"],
        "model_provider": "bedrock",
        "model_settings": {"model_id": model},
        "dependencies": list(deps),
        "priority": prio,
        "timeout": 300,
    }


def build_dast_open_tasks() -> list[dict]:
    """Render the 3-task flat-parallel open-scope DAST workflow.

    Pure-constant — open DAST takes no per-call inputs. Template
    markers (``{{run_id}}``, ``{{target_app}}``, ``{{target_url}}``,
    ``{{sandbox_env_id}}``, ``{{sast_run_id}}``) are resolved by
    ``WorkflowExecutor`` at create time.  Hypothesis-property tested
    in ``test_factories_dast_open.py`` (50 examples).
    """
    return [
        _task("gptoss-dast", _DAST_OPEN_PROMPT, _DAST_TOOLS, GPT_OSS, [], 5),
        _task("sonnet-dast", _DAST_OPEN_PROMPT, _DAST_TOOLS, SONNET, [], 5),
        _task("glm5-dast", _DAST_OPEN_PROMPT, _DAST_TOOLS, GLM5, [], 5),
    ]


# --- Workflow registration --------------------------------------------

DAST_OPEN_REGISTRATION = WorkflowConfig(
    id="dast",
    kind="workflow",
    factory="dast_open",
    name="DAST Open Scan (Workflow)",
    description=(
        "Open-scope DAST for {{target_app}}: 3 models probe the live "
        "target in parallel (GPT OSS, Sonnet, GLM 5). Broader scope, "
        "agent probes 9 vuln classes via runtime evidence "
        "(IDOR/SQLi/XSS/SSRF/CSRF/Path-Traversal/Cmd-Injection/"
        "Auth-Bypass/Mass-Assignment) and chains compounds."
    ),
    required_bricks=["graph", "security", "memory", "kb", "sandbox"],
    context_vars=[
        "target_app", "run_id", "target_url",
        "sandbox_env_id", "sast_run_id",
    ],
    execution_timeout=900,
    node_timeout=300,
)

# Back-compat export — defaults.py imports DAST_OPEN_GRAPHS as a
# 1-element list of WorkflowConfig (matches the RECON/SANDBOX/SAST
# concat shape).
DAST_OPEN_GRAPHS: list = [DAST_OPEN_REGISTRATION]
