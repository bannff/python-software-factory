"""Sandbox setup workflow — direct resource creation in LocalStack.

Migrated from kind=graph (bd python-factory-m4cp) to kind=workflow,
mirroring the recon migration (bd-s5ev). Workflow tasks cannot nest
a Swarm, so the v2 sandbox swarm + eval-tail swarm are flattened
into sibling tasks:

  resource-creator → mock-applier → sandbox-validator
    → sandbox-summary → eval-scorer

``build_sandbox_setup_tasks()`` is pure-deterministic — no per-call
inputs. ``{{run_id}}`` / ``{{target_app}}`` stay as template markers
resolved by ``WorkflowExecutor`` at create time. Tools use BARE
underscore names (``sandbox_execute``, ``graph_find_entities`` …) —
``_tool_predicate`` in strands_mcp_graph normalises dot→underscore
on mount, and per-task filters in ``_create_task_agent`` key by the
underscore form.

bd python-factory-nx4v (L3): graph reads use portable typed tools so they
work on every Graph backend.

``RT_SANDBOX_SETUP_SWARM`` and ``SANDBOX_SWARMS`` were removed in
bd python-factory-nrt5 — the meta-pipeline now composes sandbox-
setup as a nested ``type=graph`` ref instead of a v2 swarm-id ref,
so the back-compat shell has no consumers.

Workflow detail lives in skills/sandbox-ops/SKILL.md (loaded via AgentSkills, bd-2xbi).
"""
from __future__ import annotations

from factory.agent.runtime.registry_contracts import WorkflowConfig

from .models import HAIKU, SCOUT, GPT_OSS, NOVA2_LITE
from .redteam_eval_addenda import (
    EVAL_TAIL_PREAMBLE,
    EVAL_SESSION_SCORING,
    EVAL_METRICS_RECORDING,
)

# --- Per-agent prompts (thin — workflow lives in SKILL.md) -----------

_CREATOR_PROMPT = (
    "You are a sandbox setup creator.\n"
    "Run ID: {{run_id}} | App: {{target_app}}\n"
    "Agent ID: resource-creator\n\n"
    "Use these skills (call the skills tool once for each):\n"
    "1. sandbox-ops — for sandbox + AWS CLI patterns\n"
    "Read the workspace recon.json, then create each resource via "
    "sandbox_execute. When done, summarise into the task result."
)

_MOCK_PROMPT = (
    "You are a sandbox mock-applier.\n"
    "Run ID: {{run_id}} | App: {{target_app}}\n"
    "Agent ID: mock-applier\n\n"
    "Use the sandbox-ops skill (call the skills tool).\n"
    "Apply service mocks via sandbox_apply_service_mocks, then "
    "update workspace sandbox-status.json. Summarise into result."
)

_VALIDATOR_PROMPT = (
    "You are a sandbox validator.\n"
    "Run ID: {{run_id}} | App: {{target_app}}\n"
    "Agent ID: sandbox-validator\n\n"
    "Use these skills (call the skills tool once for each):\n"
    "1. sandbox-ops — for sandbox + AWS CLI patterns\n"
    "Validate created resources match the recon model, summarise."
)

_SUMMARY_PROMPT = (
    "You are a sandbox summary agent.\n"
    "Run ID: {{run_id}} | App: {{target_app}}\n"
    "Agent ID: sandbox-summary\n\n"
    "Use the sandbox-ops skill. Activate it via the skills tool, "
    "then follow its phases.\n"
    "Use graph_find_entities(entity_type='SandboxResource', "
    "properties={'run_id': '{{run_id}}'}) and "
    "graph_find_entities(entity_type='SandboxValidation', "
    "properties={'run_id': '{{run_id}}'}); then "
    "graph_add_entity type=SandboxSummary with counts."
)

# Eval-scorer prompt embeds the shared eval-tail addenda; standalone
# sandbox-setup runs leave {{metric_prefix}}/{{eval_evaluators}} as
# template markers — resolved by inject_variables at create time.
_EVAL_PROMPT = (
    EVAL_TAIL_PREAMBLE + EVAL_SESSION_SCORING + EVAL_METRICS_RECORDING
)

# --- Per-role tool sets (BARE underscore names — see docstring) ------

_CREATOR_TOOLS = [
    "sandbox_execute", "sandbox_apply_provision",
    "sandbox_workspace_dir", "sandbox_list_environments",
    "graph_find_entities", "graph_get_workflow_summary",
    "graph_add_entity",
    "file_read", "think",
]
_MOCK_TOOLS = [
    "sandbox_apply_service_mocks", "sandbox_workspace_dir",
    "sandbox_execute",
    "graph_find_entities", "graph_add_entity", "think",
]
_VALIDATOR_TOOLS = [
    "sandbox_execute", "sandbox_workspace_dir",
    "graph_find_entities", "graph_add_entity", "think",
]
_SUMMARY_TOOLS = [
    "graph_find_entities", "graph_count_entities_by_run",
    "graph_add_entity", "think",
]
_EVAL_TOOLS = [
    "graph_count_entities_by_run", "graph_get_workflow_summary",
    "graph_add_entity",
    "evals_evaluate_multi", "metrics_record", "memory_store", "think",
]


def _task(
    task_id: str, prompt: str, tools: list[str], model: str,
    deps: list[str], prio: int, skills: list[str] | None = None,
) -> dict:
    """Build one Workflow task dict. Pure — no rendering.

    bd:python-factory-2tgo1 — ``skills`` is the per-task AgentSkills
    attach list. Empty for eval-scorer (no skill ref in prompt).
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


def build_sandbox_setup_tasks() -> list[dict]:
    """Render the 5-task sandbox-setup DAG.

    Pure-constant — sandbox setup takes no per-call inputs. Template
    markers ``{{run_id}}``/``{{target_app}}`` are resolved by the
    executor at create time. Hypothesis-property tested in
    ``test_factories_sandbox_setup.py``.
    """
    # bd:python-factory-2tgo1 — per-task skills extracted from prompts.
    return [
        _task("resource-creator", _CREATOR_PROMPT, _CREATOR_TOOLS,
              HAIKU, [], 5, skills=["sandbox-ops"]),
        _task("mock-applier", _MOCK_PROMPT, _MOCK_TOOLS,
              SCOUT, ["resource-creator"], 4,
              skills=["sandbox-ops"]),
        _task("sandbox-validator", _VALIDATOR_PROMPT, _VALIDATOR_TOOLS,
              SCOUT, ["mock-applier"], 4,
              skills=["sandbox-ops"]),
        _task("sandbox-summary", _SUMMARY_PROMPT, _SUMMARY_TOOLS,
              GPT_OSS, ["sandbox-validator"], 3,
              skills=["sandbox-ops"]),
        _task("eval-scorer", _EVAL_PROMPT, _EVAL_TOOLS,
              NOVA2_LITE, ["sandbox-summary"], 2, skills=[]),
    ]


# --- Workflow registration --------------------------------------------

SANDBOX_SETUP_REGISTRATION = WorkflowConfig(
    id="sandbox-setup",
    kind="workflow",
    factory="sandbox_setup",
    name="Sandbox Setup (Workflow)",
    description=(
        "Direct resource creation in LocalStack for {{target_app}}. "
        "resource-creator → mock-applier → sandbox-validator → "
        "sandbox-summary → eval-scorer."
    ),
    required_bricks=[
        "sandbox", "graph", "memory", "evals", "metrics",
    ],
    context_vars=["run_id", "target_app"],
    tool_allowlist=None,  # bd-42dz: None ⇒ use all required_bricks tools
    execution_timeout=3600.0,
    node_timeout=1800.0,
)

# Back-compat exports — defaults.py imports SANDBOX_GRAPHS. It is a
# 1-element list of WorkflowConfig (was a list[dict] pre-m4cp).
# bd python-factory-nrt5: SANDBOX_SWARMS removed; the v2 back-compat
# RT_SANDBOX_SETUP_SWARM had no remaining consumer once redteam-
# pipeline-v2 became a hybrid graph composing sandbox-setup via
# type=graph ref.
SANDBOX_GRAPHS: list = [SANDBOX_SETUP_REGISTRATION]
