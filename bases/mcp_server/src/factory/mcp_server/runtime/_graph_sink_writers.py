"""Graph sink writer primitives — pure entity/edge writers via call_graph.

Extracted from ``graph_sink.py`` to keep that module under the 200 LOC budget.
All public entry points (``materialize``, ``set_workflow_run_id``,
``set_aggregator``) remain in ``graph_sink.py``; this file only holds
single-purpose primitives invoked from the lineage orchestrator
(``_graph_sink_lineage.py``).

These helpers take the ``call_graph`` callable as a parameter rather than
importing it from ``graph_sink`` — this preserves the test pattern of
``patch.object(graph_sink, "_call_graph")`` which rebinds the attribute on
the ``graph_sink`` module object. Routing all writes through the passed-in
callable means the patch is honoured for every helper call.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

# Type alias for the call_graph callable signature.
CallGraph = Callable[..., Any]


def now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def ensure_session(
    call_graph: CallGraph,
    session_id: str,
    principal_id: str | None,
    agent_id: str | None,
    workflow_run_id: str | None,
) -> None:
    """Idempotent write of the Session entity."""
    sid = f"session-{session_id}"
    now = now_iso()
    properties: dict[str, Any] = {
        "status": "active",
        "principal_id": principal_id or "",
        "agent_id": agent_id or "",
        "created_at": now,
        "started_at": now,
    }
    if workflow_run_id:
        properties["workflow_run_id"] = workflow_run_id
    call_graph(
        "graph_add_entity", entity_id=sid,
        entity_type="Session",
        properties=properties,
    )


def link_to_session(
    call_graph: CallGraph,
    session_id: str,
    entity_id: str,
    invocation_counter: dict[str, int],
) -> None:
    """Link Session -CONTAINS_INVOCATION{ordinal}-> ToolInvocation."""
    sid = f"session-{session_id}"
    ordinal = invocation_counter.get(session_id, 0)
    invocation_counter[session_id] = ordinal + 1
    call_graph(
        "graph_add_relationship",
        relationship_id=f"contains-{sid}-{entity_id}",
        relationship_type="CONTAINS_INVOCATION",
        source_id=sid, target_id=entity_id,
        properties={"ordinal": ordinal},
    )


def ensure_brick(call_graph: CallGraph, brick_name: str) -> None:
    """Idempotent write of the Brick entity."""
    call_graph(
        "graph_add_entity",
        entity_id=f"brick-{brick_name}",
        entity_type="Brick",
        properties={"name": brick_name, "created_at": now_iso()},
    )


def link_to_brick(call_graph: CallGraph, entity_id: str, brick_name: str) -> None:
    """Link ToolInvocation -INVOKED_ON-> Brick."""
    brick_id = f"brick-{brick_name}"
    call_graph(
        "graph_add_relationship",
        relationship_id=f"invoked-on-{entity_id}-{brick_id}",
        relationship_type="INVOKED_ON",
        source_id=entity_id,
        target_id=brick_id,
    )


def link_session_sequence(
    call_graph: CallGraph,
    session_id: str,
    entity_id: str,
    last_by_session: dict[str, str],
) -> None:
    """Link previous ToolInvocation -FOLLOWED_BY-> current (per session chain)."""
    previous_id = last_by_session.get(session_id)
    last_by_session[session_id] = entity_id
    if previous_id is None:
        return
    call_graph(
        "graph_add_relationship",
        relationship_id=f"followed-by-{previous_id}-{entity_id}",
        relationship_type="FOLLOWED_BY",
        source_id=previous_id,
        target_id=entity_id,
    )


def ensure_user(call_graph: CallGraph, principal_id: str) -> None:
    """Idempotent write of the User entity."""
    call_graph(
        "graph_add_entity",
        entity_id=f"user-{principal_id}",
        entity_type="User",
        properties={"principal_id": principal_id, "created_at": now_iso()},
    )


def link_session_initiator(
    call_graph: CallGraph,
    session_id: str,
    principal_id: str,
) -> None:
    """Link Session -INITIATED_BY-> User."""
    sid = f"session-{session_id}"
    uid = f"user-{principal_id}"
    call_graph(
        "graph_add_relationship",
        relationship_id=f"initiated-by-{sid}-{uid}",
        relationship_type="INITIATED_BY",
        source_id=sid,
        target_id=uid,
    )


def ensure_agent(call_graph: CallGraph, agent_id: str) -> None:
    """Idempotent write of the Agent entity."""
    call_graph(
        "graph_add_entity",
        entity_id=f"agent-{agent_id}",
        entity_type="Agent",
        properties={"agent_id": agent_id, "created_at": now_iso()},
    )


def link_session_agent(
    call_graph: CallGraph,
    session_id: str,
    agent_id: str,
) -> None:
    """Link Session -EXECUTED_BY-> Agent."""
    sid = f"session-{session_id}"
    aid = f"agent-{agent_id}"
    call_graph(
        "graph_add_relationship",
        relationship_id=f"executed-by-{sid}-{aid}",
        relationship_type="EXECUTED_BY",
        source_id=sid,
        target_id=aid,
    )


