"""Personalless read-only review graphs for Evals-owned gates."""
from __future__ import annotations

from factory.evals.interface import REVIEW_TOOL_SCOPE, get_review_policy

from ..runtime.graph_contracts import AgentNodeRef, GraphConfig

REVIEW_DEVTOOLS = REVIEW_TOOL_SCOPE


def _graph(graph_id: str, name: str) -> GraphConfig:
    policy = get_review_policy(graph_id)
    return GraphConfig(
        id=graph_id, name=name, description=policy.rubric,
        nodes=[AgentNodeRef(
            id="review", type="agent", agent_id=None,
            # Empty = inherit COMPANION_X_CHAT_MODEL — bare "openrouter"
            # broke non-OpenRouter deployments (same class as the persona
            # spawn regression fixed 2026-09-30).
            model="",
            system_prompt=policy.rubric, read_only=True,
            mcp_tool_allowlist=list(policy.allowed_tool_scope),
        )],
        edges=[], entry_points=["review"], max_node_executions=1,
        execution_timeout=300, node_timeout=240,
        required_bricks=["devtools", "evals", "workflow"],
    )


REVIEW_GRAPHS = [
    _graph("review-qa", "QA Review Policy"),
    _graph("review-meta", "Meta Architecture Review Policy"),
]

__all__ = ["REVIEW_DEVTOOLS", "REVIEW_GRAPHS"]
