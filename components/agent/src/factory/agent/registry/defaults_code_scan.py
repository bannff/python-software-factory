"""Vuln-class-agnostic SAST code scan workflow — parallel agents.

3 agents scan source code in parallel (GPT OSS, Sonnet, GLM 5),
hierarchy-analyzer flags inconsistencies, consolidator merges via
2/3 voting consensus, validator (GLM 5) adversarially challenges.

Parameterized by {{vuln_class}} — swaps skill, CWE focus, code
patterns, and OWASP reference. Same DAG, different focus.

bd python-factory-a4h7 migrated this from a Graph dict-of-nodes/
edges to a Workflow registration. The task-list factory
``build_sast_targeted_tasks(vuln_class)`` is registered in
``registry/factories.py:FACTORY_REGISTRY`` under key
``"sast_targeted"``. The registration carries the string registry
key (``factory="sast_targeted"``) per the meta-architect Option A
decision — registrations stay pure data, no embedded callables.

Per-task scope:
- Factory pre-renders ``{{vuln_class}}`` and bakes ``agent_id`` as
  the task_id (intrinsic per-task), keeping the factory pure over
  vuln_class. Hypothesis-property tested in test_factories.py.
- Other context vars (``{{run_id}}``, ``{{target_app}}``,
  ``{{sast_workspace}}``, ``{{target_packages}}``) stay as
  template markers and are resolved by ``WorkflowExecutor`` at
  workflow-create time using the full runtime context.

Workflow detail (phases, grounding rules, finding format) lives in
``components/agent/src/factory/agent/skills/<vuln_class>-code-scan/
SKILL.md`` and is loaded via the AgentSkills plugin (progressive
disclosure). Per-agent prompts here are intentionally thin — role
+ context + skill activation. See bd python-factory-2xbi.
"""
from __future__ import annotations

from factory.agent.executors._template import inject_variables
from factory.agent.runtime.registry_contracts import WorkflowConfig
from .models import GLM5, GPT_OSS, SONNET

# --- SAST scanner prompt (thin — workflow lives in SKILL.md) ---
_SAST_PROMPT = (
    "You are a SAST code scanner on a security red team.\n"
    "Run ID: {{run_id}} | App: {{target_app}} | "
    "Vuln class: {{vuln_class}} | Workspace: {{sast_workspace}}\n"
    "Agent ID: {{agent_id}}\n\n"
    "Use the `{{vuln_class}}-code-scan` skill for the workflow. "
    "Activate it now via the skills tool, then follow its phases.\n"
    "When done, summarize findings into the task result."
)

# --- Consolidator prompt (Tier D — coordination, no skill) ---
_CONSOLIDATOR_PROMPT = (
    "You are a finding consolidator for a SAST code scan.\n"
    "RUN ID: {{run_id}} | APP: {{target_app}} | "
    "VULN CLASS: {{vuln_class}}\n\n"
    "3 agents scanned code independently. Your job:\n"
    "1) Read each scanner's findings from the dependency results.\n"
    "2) Group by (file, function). Count distinct agent_id.\n"
    "3) 2/3+ agents agree -> CONFIRMED. 1/3 -> NEEDS_REVIEW.\n"
    "4) Use the hierarchy-analyzer's inconsistency report to\n"
    "   boost confidence for cross-endpoint patterns.\n"
    "5) Deduplicate into Finding records with verdict + reason.\n"
    "6) Emit a structured consensus summary as the task result."
)

# --- Validator prompt (Tier A — workflow in <vuln_class>-validate) ---
_VALIDATOR_PROMPT = (
    "You are a finding validator on a security red team.\n"
    "Run ID: {{run_id}} | App: {{target_app}} | "
    "Vuln class: {{vuln_class}} | Workspace: {{sast_workspace}}\n"
    "Agent ID: validator\n\n"
    "Use the `{{vuln_class}}-validate` skill for the workflow. "
    "Activate it now via the skills tool, then follow its phases.\n"
    "When done, store the validation summary."
)

# --- Hierarchy analyzer prompt (Tier D — coordination, no skill) ---
_HIERARCHY_PROMPT = (
    "You are a hierarchy analyzer for a SAST code scan.\n"
    "RUN ID: {{run_id}} | APP: {{target_app}} | VULN CLASS: {{vuln_class}}\n\n"
    "3 agents scanned code. Your job:\n"
    "1) Read scanner findings from the dependency results.\n"
    "2) Group endpoints by resource noun, compare auth patterns.\n"
    "3) Flag INCONSISTENCIES across HTTP methods on same resource.\n"
    "4) Reason for ~2 cycles, validate each inconsistency.\n"
    "5) Emit a structured hierarchy report as the task result."
)

# --- Strands tools per role. BARE NAMES (workflow.py L329-336
# filters by parent_agent.tool_registry.registry[name] using
# TOOL_SPEC.name). See bd python-factory-pfg3 / d70f27e1 (D).
_SCAN_TOOLS = ["think", "http_request", "file_read", "editor", "shell"]
_CONSOLIDATOR_TOOLS = ["think"]
_VALIDATOR_TOOLS = ["think", "file_read", "graph_add_entity",
                    "graph_add_relationship", "graph_get_findings_for_run"]


def _task(task_id: str, prompt: str, tools: list[str], model: str,
          deps: list[str], prio: int, vuln_class: str,
          skills: list[str] | None = None) -> dict:
    """Build one Workflow task dict. Pre-renders vuln_class+agent_id.

    bd:python-factory-2tgo1 — ``skills`` populates the per-task
    AgentSkills attach list (empty list for Tier-D coordination
    tasks like consolidator/hierarchy-analyzer that have no skill
    counterpart).
    """
    rendered = inject_variables(
        prompt, {"vuln_class": vuln_class, "agent_id": task_id},
    )
    return {
        "task_id": task_id,
        "description": rendered,
        "system_prompt": rendered,
        "tools": list(tools),
        "skills": list(skills or []),
        "model_provider": "bedrock",
        "model_settings": {"model_id": model},
        "dependencies": list(deps),
        "priority": prio,
        "timeout": 1800,
    }


def build_sast_targeted_tasks(vuln_class: str) -> list[dict]:
    """Render the 6-task SAST workflow for a given vuln_class.

    Pure, deterministic over ``vuln_class``.  Hypothesis-property
    tested across all 6 supported vuln_classes in
    ``test_factories.py``.  Pre-renders ``{{vuln_class}}`` and bakes
    each task's ``agent_id`` so downstream identity is stable.
    Other context vars stay as template markers — WorkflowExecutor
    resolves them with the full runtime context at create time.
    """
    # Per-task skills — prompts explicitly name these. Tier-D
    # coordination tasks (hierarchy-analyzer, consolidator) have
    # no skill counterpart; their prompts are fully inline.
    code_scan_skill = f"{vuln_class.lower()}-code-scan"
    validate_skill = f"{vuln_class.lower()}-validate"
    return [
        _task("gptoss-sast", _SAST_PROMPT, _SCAN_TOOLS, GPT_OSS, [], 5,
              vuln_class, skills=[code_scan_skill]),
        _task("sonnet-sast", _SAST_PROMPT, _SCAN_TOOLS, SONNET, [], 5,
              vuln_class, skills=[code_scan_skill]),
        _task("glm5-sast", _SAST_PROMPT, _SCAN_TOOLS, GLM5, [], 5,
              vuln_class, skills=[code_scan_skill]),
        _task("hierarchy-analyzer", _HIERARCHY_PROMPT, ["think"], SONNET,
              ["gptoss-sast", "sonnet-sast", "glm5-sast"], 4, vuln_class,
              skills=[]),
        _task("consolidator", _CONSOLIDATOR_PROMPT, _CONSOLIDATOR_TOOLS,
              SONNET, ["hierarchy-analyzer"], 3, vuln_class, skills=[]),
        _task("validator", _VALIDATOR_PROMPT, _VALIDATOR_TOOLS, GLM5,
              ["consolidator"], 2, vuln_class, skills=[validate_skill]),
    ]


# --- Workflow registration ---
SAST_TARGETED_REGISTRATION = WorkflowConfig(
    id="rt-sast-scan",
    kind="workflow",
    factory="sast_targeted",
    name="SAST Code Scan (Workflow)",
    description=(
        "3 models scan source code for {{vuln_class}} in parallel "
        "(GPT OSS, Sonnet, GLM 5). Hierarchy-analyzer flags "
        "inconsistent auth patterns. Consolidator merges via 2/3 "
        "voting. Validator (GLM 5) challenges. Parameterized by "
        "vuln_class context variable."
    ),
    required_bricks=["graph", "security", "memory", "kb"],
    context_vars=[
        "vuln_class", "target_app", "run_id",
        "target_packages", "sast_workspace",
    ],
    execution_timeout=5400,
    node_timeout=1800,
)

# Backward-compat alias: defaults.py and tests still import
# SAST_SCAN_GRAPH; the id stays "rt-sast-scan" so registry
# resolution is unchanged. CODE_SCAN_GRAPH dropped (no consumers,
# verified by `grep -r CODE_SCAN_GRAPH components/ tests/`).
SAST_SCAN_GRAPH = SAST_TARGETED_REGISTRATION
