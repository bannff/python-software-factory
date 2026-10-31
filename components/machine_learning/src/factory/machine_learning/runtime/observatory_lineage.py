"""Evidence-only lineage projection for ML training and learning activity."""
from __future__ import annotations

from typing import Any

MAX_NODES = 100
_DOMAIN_FIELDS = (
    "target_app", "profile_id", "profile_version", "workflow_type",
    "vuln_class", "domain_class", "principal_id", "session_id",
)
_EVENT_FIELDS = (
    ("graph_launched_event_id", "GraphEvent"),
    ("graph_completed_event_id", "GraphEvent"),
    ("graph_failed_event_id", "GraphEvent"),
    ("reward_event_id", "RewardEvent"),
    ("wallet_event_id", "WalletEvent"),
    ("memory_event_id", "MemoryEvent"),
    ("convergence_event_id", "ConvergenceEvent"),
)


def _node(
    node_id: str, entity_type: str, source: str, source_ref: str,
    *, entity_id: str | None, evidence: str, evidence_refs: list[str],
    domain_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "node_id": node_id, "entity_id": entity_id,
        "entity_type": entity_type, "source": source, "source_ref": source_ref,
        "evidence": evidence, "evidence_refs": evidence_refs,
        "domain_metadata": domain_metadata or {},
    }


def _edge(source: str, target: str, relation: str, evidence_ref: str) -> dict[str, Any]:
    return {
        "source": source, "target": target, "relation": relation,
        "verified": True, "evidence_refs": [evidence_ref],
    }


def _explicit_refs(record: dict[str, Any], plural: str, singular: str) -> list[str]:
    value = record.get(plural)
    if isinstance(value, list):
        return [str(item) for item in value if item]
    value = record.get(singular)
    return [str(value)] if value else []


def _receipt_lineage(
    receipt: dict[str, Any], nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]], missing: list[dict[str, Any]],
) -> None:
    run_id = str(receipt.get("run_id", ""))
    if not run_id:
        return
    run_node = f"training-run:{run_id}"
    ref = f"ml_training_runs:{run_id}"
    nodes[run_node] = _node(
        run_node, "TrainingRun", "training_receipt", ref,
        entity_id=run_id, evidence="persisted training receipt", evidence_refs=[ref],
    )
    missing_kinds: list[str] = []
    if not _explicit_refs(receipt, "dataset_refs", "dataset_id"):
        missing_kinds.append("dataset")
    if not _explicit_refs(receipt, "evaluation_refs", "evaluation_id"):
        missing_kinds.append("evaluation")
    model_path = str(receipt.get("model_path", ""))
    if model_path:
        model_node = f"model-artifact:{run_id}"
        evidence_ref = f"{run_id}:model_path"
        nodes[model_node] = _node(
            model_node, "ModelArtifact", "training_receipt", model_path,
            entity_id=None, evidence="non-empty model_path", evidence_refs=[evidence_ref],
        )
        edges.append(_edge(run_node, model_node, "PRODUCED", evidence_ref))
        missing_kinds.append("registry_model")
    else:
        missing_kinds.extend(["model_artifact", "registry_model"])
    tracker_exp = str(receipt.get("tracker_experiment_id", ""))
    tracker_run = str(receipt.get("tracker_run_id", ""))
    if tracker_run:
        tracker_node = f"tracker-run:{tracker_run}"
        evidence_ref = f"{run_id}:tracker_run_id"
        nodes[tracker_node] = _node(
            tracker_node, "TrackerRun", "training_receipt", tracker_run,
            entity_id=tracker_run, evidence="tracker_run_id field", evidence_refs=[evidence_ref],
        )
        edges.append(_edge(run_node, tracker_node, "TRACKED_AS", evidence_ref))
    if tracker_exp:
        exp_node = f"tracker-experiment:{tracker_exp}"
        evidence_ref = f"{run_id}:tracker_experiment_id"
        nodes[exp_node] = _node(
            exp_node, "TrackerExperiment", "training_receipt", tracker_exp,
            entity_id=tracker_exp, evidence="tracker_experiment_id field", evidence_refs=[evidence_ref],
        )
        if tracker_run:
            edges.append(_edge(f"tracker-run:{tracker_run}", exp_node, "IN_EXPERIMENT", evidence_ref))
    if missing_kinds:
        missing.append({"node_id": run_node, "kinds": missing_kinds})


def _event_allowed(run: dict[str, Any], field: str) -> bool:
    if field == "wallet_event_id":
        return bool(run.get("wallet_id") or run.get("transaction_id"))
    if field == "memory_event_id":
        return bool(run.get("memory_id") or run.get("summary_type"))
    if field == "convergence_event_id":
        return any(run.get(key) is not None for key in ("metric_id", "metrics_recorded", "converged"))
    return True


def _learning_lineage(
    run: dict[str, Any], nodes: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]], missing: list[dict[str, Any]],
) -> None:
    run_id = str(run.get("workflow_run_id") or run.get("run_id") or "")
    if not run_id:
        return
    run_node = f"workflow-run:{run_id}"
    domain = {key: run.get(key) for key in _DOMAIN_FIELDS if run.get(key) not in (None, "")}
    nodes[run_node] = _node(
        run_node, "WorkflowRun", "learning_projection", run_id,
        entity_id=run_id, evidence="stitched canonical event IDs",
        evidence_refs=[str(item.get("event_id")) for item in run.get("event_history", []) if item.get("event_id")],
        domain_metadata=domain,
    )
    for field, entity_type in _EVENT_FIELDS:
        event_id = run.get(field)
        if not event_id or not _event_allowed(run, field):
            continue
        event_id = str(event_id)
        event_node = f"event:{event_id}"
        evidence_ref = f"{run_id}:{field}"
        nodes[event_node] = _node(
            event_node, entity_type, "learning_event", event_id,
            entity_id=event_id, evidence=f"explicit {field}", evidence_refs=[evidence_ref],
            domain_metadata=domain,
        )
        edges.append(_edge(run_node, event_node, "HAS_EVENT", evidence_ref))
        if entity_type == "GraphEvent" and run.get("graph_id"):
            graph_id = str(run["graph_id"])
            graph_node = f"graph:{graph_id}"
            nodes[graph_node] = _node(
                graph_node, "Graph", "learning_event", graph_id,
                entity_id=graph_id, evidence="graph_id plus graph-event evidence",
                evidence_refs=[evidence_ref], domain_metadata=domain,
            )
            edges.append(_edge(event_node, graph_node, "REFERENCES", evidence_ref))
    absent = [
        kind for kind, plural, singular in (
            ("dataset", "dataset_refs", "dataset_id"),
            ("evaluation", "evaluation_refs", "evaluation_id"),
            ("model", "model_refs", "model_id"),
        ) if not _explicit_refs(run, plural, singular)
    ]
    if absent:
        missing.append({"node_id": run_node, "kinds": absent})


def build_lineage(receipts: list[dict[str, Any]], learning_runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Return deterministic, bounded lineage with no dangling edges."""
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for receipt in receipts:
        _receipt_lineage(receipt, nodes, edges, missing)
    for run in learning_runs:
        _learning_lineage(run, nodes, edges, missing)
    ordered_nodes = [nodes[key] for key in sorted(nodes)]
    truncated = len(ordered_nodes) > MAX_NODES
    kept_nodes = ordered_nodes[:MAX_NODES]
    kept_ids = {node["node_id"] for node in kept_nodes}
    kept_edges = [edge for edge in edges if edge["source"] in kept_ids and edge["target"] in kept_ids]
    return {
        "nodes": kept_nodes,
        "edges": sorted(kept_edges, key=lambda edge: (edge["source"], edge["target"], edge["relation"])),
        "missing_links": [item for item in missing if item["node_id"] in kept_ids],
        "truncated": truncated,
        "truncated_nodes": max(0, len(ordered_nodes) - len(kept_nodes)),
        "dropped_edges": len(edges) - len(kept_edges),
        "max_nodes": MAX_NODES,
    }


__all__ = ["MAX_NODES", "build_lineage"]
