"""Graph sink lineage orchestration — composes writer primitives.

Builds the ``ToolInvocation`` properties dict and orchestrates the lineage
edges (Brick, Session, User, Agent) for a single materialised invocation.

Separated from ``_graph_sink_writers.py`` so each file stays well under the
200 LOC budget. Writer primitives are pure (one entity / one edge per call);
this file composes them into the full lineage write performed by every
``materialize()`` invocation.
"""
from __future__ import annotations

import json
from typing import Any

from . import _graph_sink_run as _r
from . import _graph_sink_writers as _w


def build_invocation_props(
    entity_id: str, brick_name: str, tool_name: str, success: bool,
    latency_ms: float, safe_error: str | None,
    session_id: str | None, principal_id: str | None,
    workflow_run_id: str | None, invocation_type: str,
    args_summary: dict | None, caller: str | None,
    result_summary: dict | None,
    sequence: int | None = None,
) -> dict[str, Any]:
    """Build the properties dict for a ToolInvocation entity write."""
    props: dict[str, Any] = {
        "id": entity_id, "brick_name": brick_name,
        "tool_name": tool_name, "success": success,
        "latency_ms": latency_ms, "error": safe_error,
        "session_id": session_id,
        "principal_id": principal_id,
        "workflow_run_id": workflow_run_id,
        "invocation_type": invocation_type,
        "created_at": _w.now_iso(),
    }
    if sequence is not None:
        props["sequence"] = sequence
    # Serialize dicts as JSON strings for Neo4j compatibility
    if args_summary:
        props["args_summary"] = json.dumps(args_summary)
    if caller:
        props["caller"] = caller
    if result_summary:
        props["result_summary"] = json.dumps(result_summary)
    return props


def write_invocation_with_lineage(
    call_graph: _w.CallGraph,
    entity_id: str,
    props: dict[str, Any],
    brick_name: str,
    session_id: str | None,
    principal_id: str | None,
    agent_id: str | None,
    workflow_run_id: str | None,
    invocation_counter: dict[str, int],
    last_by_session: dict[str, str],
    run_invocation_counter: dict[str, int] | None = None,
    last_by_run: dict[str, str] | None = None,
) -> None:
    """Write the ToolInvocation entity plus all its lineage edges."""
    call_graph(
        "graph_add_entity", entity_id=entity_id,
        entity_type="ToolInvocation", properties=props,
    )
    _w.ensure_brick(call_graph, brick_name)
    _w.link_to_brick(call_graph, entity_id, brick_name)
    # Workflow-run lineage written FIRST so per-session FOLLOWED_BY wins
    # if the underlying graph backend (e.g. nx.DiGraph) deduplicates edges
    # by (source, target). Within a single session, NEXT_IN_RUN and
    # FOLLOWED_BY share endpoints; FOLLOWED_BY semantics take precedence
    # for tests/queries that depend on it.
    if workflow_run_id and run_invocation_counter is not None and last_by_run is not None:
        _r.ensure_workflow_run(call_graph, workflow_run_id, principal_id)
        if principal_id:
            _r.link_run_initiator(call_graph, workflow_run_id, principal_id)
        if session_id:
            _r.link_run_session(call_graph, workflow_run_id, session_id)
        sequence = props.get("sequence", 0)
        _r.link_run_sequence(
            call_graph, workflow_run_id, entity_id, last_by_run, sequence,
        )
    if session_id:
        _w.ensure_session(
            call_graph, session_id, principal_id, agent_id, workflow_run_id,
        )
        _w.link_to_session(call_graph, session_id, entity_id, invocation_counter)
        _w.link_session_sequence(
            call_graph, session_id, entity_id, last_by_session,
        )
        if principal_id:
            _w.ensure_user(call_graph, principal_id)
            _w.link_session_initiator(call_graph, session_id, principal_id)
        if agent_id:
            _w.ensure_agent(call_graph, agent_id)
            _w.link_session_agent(call_graph, session_id, agent_id)
