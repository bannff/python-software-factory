"""Read-only Dataset Researcher persona and fixed fan-in graph."""
from __future__ import annotations

from ..runtime.registry_contracts import AgentConfig, GraphConfig

DATASET_RESEARCHER = AgentConfig(
    id="dataset-researcher",
    name="Dataset Researcher",
    model="",  # inherit COMPANION_X_CHAT_MODEL — bare "openrouter" broke spawns on non-OpenRouter deployments
    system_prompt=(
        "You are a read-only dataset research specialist. Follow the node's "
        "assigned skill and return only evidence-backed structured output. "
        "Never publish, mutate, submit, cancel, train, or execute jobs."
    ),
    tools=[],
    skills=[],
    exact_tools=True,
    description="Plans, researches, and drafts dataset evidence without publishing.",
)

_RESEARCH_TOOLS = [
    "dataset_get_capabilities", "dataset_describe_config_schema",
    "dataset_get_job", "dataset_get_artifact", "dataset_resolve_artifact",
]
_RESEARCH_NODES = [
    ("requirements", "dataset-research-requirements"),
    ("sources", "dataset-research-sources"),
    ("quality", "dataset-research-quality"),
    ("provenance", "dataset-research-provenance"),
]

DATASET_RESEARCH_GRAPH = GraphConfig.model_validate({
    "id": "dataset-research",
    "name": "Dataset Research",
    "description": "Planner, four parallel read-only researchers, and typed drafter.",
    "entry_points": ["planner"],
    "terminal_node": "drafter",
    "resumable": True,
    "max_node_executions": 6,
    "execution_timeout": 1800.0,
    "node_timeout": 300.0,
    "nodes": [
        {
            "id": "planner", "type": "agent", "agent_id": "dataset-researcher",
            "system_prompt": "Plan four dataset research tracks. Use the dataset-research-plan skill.",
            "skills": ["dataset-research-plan"], "mcp_tool_allowlist": [],
            "read_only": True, "output_schema": "research-plan-v1",
        },
        *[
            {
                "id": node_id, "type": "agent", "agent_id": "dataset-researcher",
                "system_prompt": f"Research the {node_id} track. Use the {skill} skill.",
                "skills": [skill], "mcp_tool_allowlist": _RESEARCH_TOOLS,
                "read_only": True, "output_schema": "research-evidence-v1",
            }
            for node_id, skill in _RESEARCH_NODES
        ],
        {
            "id": "drafter", "type": "agent", "agent_id": "dataset-researcher",
            "system_prompt": "Synthesize all four evidence tracks using dataset-research-draft.",
            "skills": ["dataset-research-draft"], "mcp_tool_allowlist": [],
            "read_only": True, "output_schema": "research-draft-v1",
        },
    ],
    "edges": [
        *[{"source": "planner", "target": node_id} for node_id, _ in _RESEARCH_NODES],
        *[
            {"source": node_id, "target": "drafter", "condition": "all-predecessors-valid"}
            for node_id, _ in _RESEARCH_NODES
        ],
    ],
})

DATASET_RESEARCH_AGENTS = [DATASET_RESEARCHER]
DATASET_RESEARCH_GRAPHS = [DATASET_RESEARCH_GRAPH]

__all__ = [
    "DATASET_RESEARCHER", "DATASET_RESEARCH_AGENTS", "DATASET_RESEARCH_GRAPH",
    "DATASET_RESEARCH_GRAPHS",
]
