"""Deterministic registered-persona to one-node GraphConfig projection."""
from __future__ import annotations

import hashlib
from typing import Any

from ..graph_contracts import AgentNodeRef, GraphConfig


def persona_graph(
    registry: Any, agent_id: str, output_schema: str | None = None,
) -> GraphConfig:
    """Build one stable graph definition without adding durable registry state."""
    if registry.get(agent_id) is None:
        raise ValueError("unknown_agent_id")
    digest = hashlib.sha256(agent_id.encode("utf-8")).hexdigest()[:16]
    return GraphConfig(
        id=f"background-persona-{digest}",
        name=f"Background {agent_id}",
        description="One registered persona executed as a durable Workflow attempt.",
        nodes=[AgentNodeRef(
            id=agent_id, type="agent", agent_id=agent_id,
            output_schema=output_schema,
        )],
        entry_points=[agent_id], terminal_node=agent_id,
        max_node_executions=1, resumable=True,
    )


__all__ = ["persona_graph"]
