"""Bounded context-to-Strands trace attribute projection."""
from __future__ import annotations

from typing import Any

_CONTEXT_ATTRIBUTES = {
    "run_id": "run.id",
    "trace_id": "trace.id",
    "span_id": "span.id",
    "parent_span_id": "parent.span.id",
    "session_id": "session.id",
    "graph_id": "graph.id",
    "swarm_id": "swarm.id",
}


def trace_attributes_from_context(
    context: dict[str, Any] | None, agent_id: str | None = None,
) -> dict[str, str]:
    """Return only bounded scalar IDs supported by native Agent config."""
    source = context if isinstance(context, dict) else {}
    attributes: dict[str, str] = {}
    run_id = source.get("run_id") or source.get("workflow_run_id")
    for source_key, attribute_key in _CONTEXT_ATTRIBUTES.items():
        value = run_id if source_key == "run_id" else source.get(source_key)
        if value is None or isinstance(value, (dict, list, tuple, set)):
            continue
        text = str(value).strip()
        if text and len(text) <= 256:
            attributes[attribute_key] = text
    session = attributes.get("session.id")
    if session:
        attributes["gen_ai.conversation.id"] = session
    if agent_id:
        text = str(agent_id).strip()
        if text and len(text) <= 256:
            attributes["agent.id"] = text
    return attributes


__all__ = ["trace_attributes_from_context"]
