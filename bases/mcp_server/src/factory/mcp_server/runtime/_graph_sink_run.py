"""WorkflowRun lineage writers — anchors invocations into a run-scoped path.

Separated from ``_graph_sink_writers.py`` to keep both files under 200 LOC.
WorkflowRun is the root anchor that lets us select all telemetry for a single
run; NEXT_IN_RUN edges chain ToolInvocations into a connected path even when
they span multiple sessions.
"""
from __future__ import annotations

from typing import Any

from ._graph_sink_writers import CallGraph, now_iso


def ensure_workflow_run(
    call_graph: CallGraph,
    workflow_run_id: str,
    principal_id: str | None,
) -> None:
    """Idempotent write of the WorkflowRun entity (root anchor for a run)."""
    properties: dict[str, Any] = {
        "run_id": workflow_run_id,
        "status": "running",
        "started_at": now_iso(),
        "created_at": now_iso(),
    }
    if principal_id:
        properties["principal_id"] = principal_id
    call_graph(
        "graph_add_entity",
        entity_id=f"workflow-run-{workflow_run_id}",
        entity_type="WorkflowRun",
        properties=properties,
    )


def link_run_session(
    call_graph: CallGraph,
    workflow_run_id: str,
    session_id: str,
) -> None:
    """Link WorkflowRun -CONTAINS_SESSION-> Session."""
    rid = f"workflow-run-{workflow_run_id}"
    sid = f"session-{session_id}"
    call_graph(
        "graph_add_relationship",
        relationship_id=f"contains-session-{rid}-{sid}",
        relationship_type="CONTAINS_SESSION",
        source_id=rid,
        target_id=sid,
    )


def link_run_initiator(
    call_graph: CallGraph,
    workflow_run_id: str,
    principal_id: str,
) -> None:
    """Link WorkflowRun -INITIATED_BY-> User."""
    rid = f"workflow-run-{workflow_run_id}"
    uid = f"user-{principal_id}"
    call_graph(
        "graph_add_relationship",
        relationship_id=f"initiated-by-{rid}-{uid}",
        relationship_type="INITIATED_BY",
        source_id=rid,
        target_id=uid,
    )


def link_run_sequence(
    call_graph: CallGraph,
    workflow_run_id: str,
    entity_id: str,
    last_by_run: dict[str, str],
    sequence: int,
) -> None:
    """Link previous ToolInvocation -NEXT_IN_RUN{run_id, sequence}-> current.

    Run-scoped chain (different from FOLLOWED_BY which is session-scoped).
    Multiple sessions inside one run still produce a single connected path.
    """
    previous_id = last_by_run.get(workflow_run_id)
    last_by_run[workflow_run_id] = entity_id
    if previous_id is None:
        return
    call_graph(
        "graph_add_relationship",
        relationship_id=f"next-in-run-{previous_id}-{entity_id}",
        relationship_type="NEXT_IN_RUN",
        source_id=previous_id,
        target_id=entity_id,
        properties={"run_id": workflow_run_id, "sequence": sequence},
    )
