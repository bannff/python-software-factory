"""LLMAJ curation: judge learning nodes and suppress bad recall."""
from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from typing import Any

from ..learning_result import normalize_learning_result
from ..mcp_result import legacy_memory_record, successful_data
from ..models import Event

logger = logging.getLogger(__name__)
_SUPPRESSING_VERDICTS = {"harmful", "redundant"}


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _score(result: dict[str, Any]) -> float:
    for key in ("scalar", "score", "avg_score", "average_score"):
        value = result.get(key)
        if isinstance(value, (int, float)):
            return max(0.0, min(1.0, float(value)))
    raw = result.get("raw") if isinstance(result.get("raw"), dict) else {}
    scoring = raw.get("scoring") if isinstance(raw.get("scoring"), dict) else {}
    value = scoring.get("f1")
    return max(0.0, min(1.0, float(value))) if isinstance(value, (int, float)) else 0.0


def _verdict(score: float) -> str:
    if score >= 0.60:
        return "useful"
    return "redundant" if score >= 0.35 else "harmful"


def _props(entity: Any) -> dict[str, Any]:
    properties = _field(entity, "properties")
    return dict(properties) if isinstance(properties, Mapping) else {}


def _neighbor_summary(neighbors: list[Any]) -> str:
    parts = [
        f"{_field(neighbor, 'type', '')}:{_field(neighbor, 'id', '')}"
        for neighbor in neighbors[:8]
    ]
    return ", ".join(parts) if parts else "no related graph nodes"


def _curation_context(
    content: str, domain: str, run_id: str, neighborhood: str,
) -> tuple[str, str]:
    return (
        "Judge whether this stored agent learning should keep being recalled. "
        "Use graph evidence; redundant or harmful learnings should be suppressed.",
        f"Learning: {content}\nDomain: {domain}\nRun: {run_id}\n"
        f"Graph neighborhood: {neighborhood}\n"
        "High quality means specific, actionable, and non-duplicative.",
    )


_NODE_WAIT_ATTEMPTS = 5
_NODE_WAIT_SECONDS = 2.0


def _await_learning_node(invoker: Any, learning_node_id: str) -> Any:
    """Poll for the .2 lineage node, tolerating the memory.learning_stored race.

    .2 (learning_lineage_dispatch) and .3 (learning_curation_dispatch) both
    subscribe to memory.learning_stored and run in independent daemon threads
    (dispatch.py) with no ordering guarantee. If .3 wins the race it must not
    permanently skip — it retries briefly for .2 to create the node instead of
    treating a timing loss as a missing node.
    """
    entity = None
    for attempt in range(_NODE_WAIT_ATTEMPTS):
        result = successful_data(invoker("graph_get_entity", entity_id=learning_node_id))
        if result is not None and result.get("found") and result.get("entity") is not None:
            entity = result["entity"]
            return entity
        if attempt < _NODE_WAIT_ATTEMPTS - 1:
            time.sleep(_NODE_WAIT_SECONDS)
    return entity


def handle_learning_curation(event: Event, invoker: Any) -> dict[str, Any]:
    """Judge a newly-stored learning and mark its graph node for recall use."""
    payload = event.payload
    memory_id = payload.get("memory_id")
    if not memory_id:
        return {"skipped": True, "reason": "no_memory_id"}

    learning_node_id = f"learning-{memory_id}"
    curation_node_id = f"curation-{memory_id}-{event.id}"
    try:
        entity = _await_learning_node(invoker, learning_node_id)
        if entity is None:
            return {"skipped": True, "reason": "learning_node_missing", "memory_id": memory_id}
        learning_props = _props(entity)

        memory_result = invoker("memory_get", memory_id=memory_id)
        memory_data = successful_data(memory_result)
        memory = None
        if isinstance(memory_data, Mapping):
            memory = legacy_memory_record(memory_data.get("memory"))
            if memory is None:
                memory = legacy_memory_record(memory_data)
        if memory is None:
            memory = legacy_memory_record(memory_result)
        if memory is None:
            return {"skipped": True, "reason": "memory_missing", "memory_id": memory_id}
        content = str(memory.get("content") or "")
        if not content:
            return {"skipped": True, "reason": "memory_missing", "memory_id": memory_id}

        neighbor_data = successful_data(invoker(
            "graph_get_neighbors", entity_id=learning_node_id, direction="both",
        )) or {}
        neighbors_value = neighbor_data.get("neighbors", [])
        neighbors = list(neighbors_value) if isinstance(neighbors_value, list) else []
        run_id = learning_props.get("run_id") or payload.get("run_id") or ""
        domain = learning_props.get("domain_class") or payload.get("domain_class") or "curation"
        input_summary, output_summary = _curation_context(
            content, str(domain), str(run_id), _neighbor_summary(neighbors),
        )
        result = normalize_learning_result(invoker(
            "learning_compute_reward",
            run_id=f"curation-{memory_id}",
            domain_class="curation",
            workflow_type="learning-curation",
            input_summary=input_summary,
            output_summary=output_summary,
        ))
        if result is None:
            return {"skipped": True, "reason": "curation_failed", "memory_id": memory_id}
        if not result.get("source_id"):
            return {"skipped": True, "reason": "curation_abstained", "memory_id": memory_id}

        score = _score(result)
        verdict = _verdict(score)
        suppressed = verdict in _SUPPRESSING_VERDICTS
        now = time.time()
        updated_props = {
            **learning_props,
            "curated_verdict": verdict,
            "curation_score": score,
            "suppressed": suppressed,
            "curated_at": now,
            "curation_source": result.get("source_id", ""),
        }
        invoker("graph_update_entity", entity_id=learning_node_id, properties=updated_props)
        invoker(
            "graph_add_entity",
            entity_id=curation_node_id,
            entity_type="CurationDecision",
            properties={
                "memory_id": memory_id,
                "learning_node_id": learning_node_id,
                "verdict": verdict,
                "score": score,
                "suppressed": suppressed,
                "source_id": result.get("source_id", ""),
                "timestamp": now,
            },
        )
        invoker(
            "graph_add_relationship",
            relationship_id=f"curated-by-{memory_id}-{event.id}",
            relationship_type="curated_by",
            source_id=learning_node_id,
            target_id=curation_node_id,
        )
        return {
            "status": "learning_curated",
            "memory_id": memory_id,
            "learning_node_id": learning_node_id,
            "curation_node_id": curation_node_id,
            "verdict": verdict,
            "score": score,
            "suppressed": suppressed,
        }
    except Exception as exc:  # noqa: BLE001 — curation must not break memory
        logger.warning("learning curation failed (isolated): %s", exc)
        return {
            "status": "curation_error",
            "memory_id": memory_id,
            "learning_node_id": learning_node_id,
            "error": "curation_failed",
        }
