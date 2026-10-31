"""Workflow event_bus → AG-UI translation for nested chat workflows.

The chat agent's ``ChatStreamEvent`` covers the LLM's internal loop.
When the agent invokes a workflow tool (``invoke_swarm_async``,
``invoke_graph_async``), the executor emits ``swarm.*`` / ``graph.*`` /
``rl.*`` events through the in-process ``mcp_utils.event_bus``. Those
events arrive on the same merged stream as chat events and need their
own translation table.

Pure pass-through: this thin shim normalises an ``event_bus`` payload
into the dict shape expected by the existing
``factory.ui.runtime.ag_ui_mapper.map_event`` and delegates. Lives in
the api base because nested-workflow translation is a transport-level
concern (the events brick already publishes; the ui brick already
maps); we just bridge the names.
"""
from __future__ import annotations

from typing import Any

from factory.ui.runtime.ag_ui_mapper import map_event

# Map raw event_bus event_type to the brick-internal type the ui mapper knows.
# Anything not in the table falls through to ``map_event`` which emits a
# ``CUSTOM`` AG-UI event — safer than dropping unknown lifecycle data.
_WORKFLOW_TYPE_ALIASES = {
    "swarm.node_start": "agent.step.start",
    "graph.node_start": "agent.step.start",
    "swarm.node_stop": "agent.step.complete",
    "graph.node_stop": "agent.step.complete",
}


def map_workflow_event(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Translate one ``event_bus`` event to AG-UI events.

    ``raw`` carries one of two shapes:

    * Tool-invocation event (``mcp_server.runtime.instrumentation``):
      ``{brick, tool, success, latency_ms, ts, ...}``.
    * Domain event (``events.runtime.bridge``):
      ``{event_type, source, payload, ts}``.

    We only translate domain events here; tool-invocation events are
    rendered by the chat agent's tool-call cards already.
    """
    if not isinstance(raw, dict):
        return []
    event_type = raw.get("event_type")
    if isinstance(event_type, str) and event_type.startswith("devtools.command."):
        return []
    if not event_type:
        # Tool-invocation event from instrumentation — the chat path
        # already renders these as TOOL_CALL_*; drop to avoid duplicates.
        return []
    payload = raw.get("payload") or {}
    canonical = _WORKFLOW_TYPE_ALIASES.get(event_type, event_type)
    return map_event({
        "type": canonical,
        "payload": payload,
        "session_id": str(
            payload.get("correlation_id") or payload.get("request_id")
            or raw.get("correlation_id") or raw.get("request_id")
            or payload.get("run_id", "")
        ),
    })


__all__ = ["map_workflow_event"]
