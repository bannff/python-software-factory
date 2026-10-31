"""Opportunistic graph sync for workflow runs and activity."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from factory.mcp_utils.interface import normalize_correlation


def _get_invoker():
    try:
        from factory.mcp_utils.interface import get_service

        invoker = get_service("tool_invoker")
        if invoker is not None:
            return invoker
    except Exception:
        pass
    return None


def _invoke(tool_name: str, **kwargs: Any) -> Any:
    invoker = _get_invoker()
    if invoker is None:
        return None
    try:
        return invoker(tool_name, **kwargs)
    except Exception:
        return None


def workflow_entity_id(run_id: str) -> str:
    return f"workflow-run-{run_id}"


def sync_run(run: dict[str, Any], *sources: Any) -> None:
    run_id = str(run.get("run_id", ""))
    workflow_id = str(run.get("workflow_id", ""))
    if not run_id:
        return

    correlation = normalize_correlation(
        run, *sources, {"entity_id": workflow_entity_id(run_id)},
        authoritative_run_id=run_id,
    )
    properties = {
        **run,
        **correlation,
        "entity_id": workflow_entity_id(run_id),
    }
    _invoke(
        "graph_graph_add_entity",
        entity_id=workflow_entity_id(run_id),
        entity_type="WorkflowRun",
        properties=properties,
    )

    if workflow_id:
        definition_id = f"workflow-def-{workflow_id}"
        _invoke(
            "graph_graph_add_entity",
            entity_id=definition_id,
            entity_type="WorkflowDefinition",
            properties={
                "workflow_id": workflow_id,
                "name": str(run.get("workflow_name", workflow_id)),
                "version": run.get("workflow_version"),
            },
        )
        _invoke(
            "graph_graph_add_relationship",
            relationship_id=f"workflow-def-{run_id}",
            relationship_type="RUNS_WORKFLOW",
            source_id=workflow_entity_id(run_id),
            target_id=definition_id,
        )

    related_ids = {
        correlation.get("env_id"): lambda value: f"sandbox-env-{value}",
        correlation.get("game_id"): lambda value: f"game-{value}",
    }
    for raw_value, make_entity_id in related_ids.items():
        if raw_value:
            target_id = make_entity_id(raw_value)
            _invoke(
                "graph_graph_add_relationship",
                relationship_id=f"workflow-correlation-{run_id}-{target_id}",
                relationship_type="CORRELATED_WITH",
                source_id=workflow_entity_id(run_id),
                target_id=target_id,
            )


def sync_activity(event_type: str, payload: dict[str, Any], *sources: Any) -> None:
    run_id = str(payload.get("run_id", ""))
    if not run_id:
        return

    correlation = normalize_correlation(
        payload, *sources, {"entity_id": workflow_entity_id(run_id)},
        authoritative_run_id=run_id,
    )
    activity_id = f"workflow-event-{run_id}-{uuid4().hex[:8]}"
    _invoke(
        "graph_graph_add_entity",
        entity_id=activity_id,
        entity_type="WorkflowEvent",
        properties={
            **payload,
            **correlation,
            "event_type": event_type,
            "activity_id": activity_id,
        },
    )
    _invoke(
        "graph_graph_add_relationship",
        relationship_id=f"workflow-activity-{activity_id}",
        relationship_type="HAS_ACTIVITY",
        source_id=workflow_entity_id(run_id),
        target_id=activity_id,
    )