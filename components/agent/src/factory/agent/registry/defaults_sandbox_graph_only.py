"""Sandbox setup — graph-only variant (parallel independent agents).

3 parallel agent nodes (resource-creator, mock-applier, validator)
→ summary agent. Each works independently on its domain.

Context variables: {{run_id}}, {{target_app}}

Workflow detail (sandbox CLI, AWS CLI patterns, mock config,
validation commands) lives in skills/sandbox-ops/SKILL.md — loaded via the
AgentSkills plugin. See bd python-factory-2xbi.
"""
from __future__ import annotations

from .models import HAIKU, SONNET, SCOUT, GPT_OSS

_CREATOR_PROMPT = (
    "You are a sandbox resource creator.\n"
    "Run ID: {{run_id}} | App: {{target_app}}\n"
    "Agent ID: {{agent_id}}\n\n"
    "Use these skills (call the skills tool once for each):\n"
    "1. sandbox-ops — for sandbox + AWS CLI patterns\n"
    "When done, hand off via swarm/graph protocol."
)

_MOCK_PROMPT = (
    "You are a sandbox mock-applier.\n"
    "Run ID: {{run_id}} | App: {{target_app}}\n"
    "Agent ID: {{agent_id}}\n\n"
    "Use these skills (call the skills tool once for each):\n"
    "1. sandbox-ops — for sandbox + AWS CLI patterns\n"
    "When done, hand off via swarm/graph protocol."
)

_VALIDATOR_PROMPT = (
    "You are a sandbox validator.\n"
    "Run ID: {{run_id}} | App: {{target_app}}\n"
    "Agent ID: {{agent_id}}\n\n"
    "Use these skills (call the skills tool once for each):\n"
    "1. sandbox-ops — for sandbox + AWS CLI patterns\n"
    "When done, hand off via swarm/graph protocol."
)

_SUMMARY_PROMPT = (
    "You are the sandbox summary agent.\n"
    "Run ID: {{run_id}} | App: {{target_app}}\n"
    "Agent ID: summary\n\n"
    "Use the sandbox-ops skill. Activate it via the skills tool, "
    "then follow its phases.\n"
    "Use graph_find_entities(entity_type='SandboxResource', "
    "properties={'run_id': '{{run_id}}'}) and "
    "graph_find_entities(entity_type='SandboxValidation', "
    "properties={'run_id': '{{run_id}}'}); then "
    "graph_add_entity type=SandboxSummary with counts."
)

SANDBOX_GRAPH_ONLY: dict = {
    "id": "rt-sandbox-setup-graph",
    "name": "Sandbox Setup (Parallel Agents Graph)",
    "description": (
        "3 parallel agents (creator, mock-applier, validator) "
        "→ Sonnet summary. Independent sandbox setup."
    ),
    "required_bricks": ["graph", "security", "memory", "kb"],
    "context_vars": ["run_id", "target_app"],
    "entry_points": [
        "resource-creator", "mock-applier", "validator",
    ],
    "nodes": [
        # bd:python-factory-2tgo1 — every prompt names sandbox-ops.
        {"id": "resource-creator", "type": "agent", "model": "",
         "description": "Creates AWS resources in LocalStack.",
         "system_prompt": _CREATOR_PROMPT,
         "skills": ["sandbox-ops"],
         "tools": ["think"],
         "context": {"agent_id": "resource-creator"}},
        {"id": "mock-applier", "type": "agent", "model": "",
         "description": "Applies service mocks.",
         "system_prompt": _MOCK_PROMPT,
         "skills": ["sandbox-ops"],
         "tools": ["think"],
         "context": {"agent_id": "mock-applier"}},
        {"id": "validator", "type": "agent", "model": "",
         "description": "Validates sandbox matches target.",
         "system_prompt": _VALIDATOR_PROMPT,
         "skills": ["sandbox-ops"],
         "tools": ["think"],
         "context": {"agent_id": "validator"}},
        {"id": "summary", "type": "agent", "model": "",
         "description": "Summarizes sandbox state.",
         "system_prompt": _SUMMARY_PROMPT,
         "skills": ["sandbox-ops"],
         "tools": ["think"]},
    ],
    "edges": [
        {"source": "resource-creator", "target": "summary"},
        {"source": "mock-applier", "target": "summary"},
        {"source": "validator", "target": "summary"},
    ],
    "max_node_executions": 3,
    "execution_timeout": 1800,
    "node_timeout": 600,
}
