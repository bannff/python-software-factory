"""Public preparation boundary for immutable Agent execution manifests."""
from __future__ import annotations

from typing import Any

from pydantic import JsonValue

from .base import json_object
from .canonical import canonical_bytes, seal_manifest, sha256
from .compile_graph import compile_config, freeze_edges
from .models import (
    ExecutionManifestV1, GraphLimits, InvocationManifest, ManifestOrigin,
    ProvenanceRecord,
)
from .plugin_freeze import graph_hooks

REGISTERED_GRAPH_IDS = (
    "rt-scan-idor", "sandbox-setup",
    "eval-rl-feedback", "rt-sast-scan", "sast", "dast",
    "rt-sast-scan-hybrid", "rt-scan-idor-hybrid",
    "rt-sandbox-setup-graph", "rt-sandbox-setup-hybrid",
    "rt-sast-sonnet", "rt-sast-haiku", "rt-sast-nova2", "can-pipeline",
    "dataset-research", "review-qa", "review-meta",
)


def _registries() -> tuple[dict[str, Any], dict[str, Any]]:
    from factory.agent.registry.defaults import GRAPHS_TYPED, SWARMS_TYPED

    graphs = {item.id: item for item in GRAPHS_TYPED}
    swarms = {item.id: item for item in SWARMS_TYPED}
    if tuple(graphs) != REGISTERED_GRAPH_IDS:
        raise RuntimeError("registered graph matrix changed; update manifest compiler deliberately")
    return graphs, swarms


def _node_bound(compiled: Any) -> int:
    if compiled.max_node_executions is not None:
        return compiled.max_node_executions
    from factory.agent.runtime.graph_bounds import default_max_node_executions

    default = default_max_node_executions(len(compiled.nodes))
    if compiled.max_cycles is None:
        return default
    translated = max(len(compiled.nodes), 1) * (compiled.max_cycles + 1)
    return max(default, translated)


def _langgraph_sdk_version() -> str:
    """Dormant-runtime laziness: langgraph lives in langgraph-legacy."""
    from importlib.metadata import version

    return version("langgraph")


def prepare_execution_manifest(
    config: Any, task: JsonValue, context: dict[str, Any], *,
    invocation_state: dict[str, Any] | None = None,
    origin_kind: str = "dynamic",
) -> ExecutionManifestV1:
    """Compile one GraphConfig/WorkflowConfig while mutable registries are available."""
    graphs, swarms = _registries()
    graph_map = {**graphs, config.id: config}
    canonical_context = json_object(context)
    compiled = compile_config(config, canonical_context, graph_map, swarms)
    definition = config.model_dump(mode="json")
    provenance = (ProvenanceRecord(
        kind="graph-definition", identity=config.id,
        digest=sha256(canonical_bytes(definition)),
    ),)
    manifest = ExecutionManifestV1(
        origin=ManifestOrigin(kind=origin_kind, source_id=config.id),
        graph_id=config.id, graph_name=config.name,
        description=compiled.description, nodes=compiled.nodes,
        edges=freeze_edges(compiled), entry_points=compiled.entries,
        limits=GraphLimits(
            max_node_executions=_node_bound(compiled),
            execution_timeout=compiled.execution_timeout,
            node_timeout=compiled.node_timeout,
        ), hooks=graph_hooks(config.id, canonical_context),
        invocation=InvocationManifest(
            task=task, context=canonical_context,
            invocation_state=json_object(invocation_state or {}),
        ), sdk_version=_langgraph_sdk_version(), provenance=provenance,
    )
    return seal_manifest(manifest)


def prepare_registered_execution_manifest(
    graph_id: str, task: JsonValue, context: dict[str, Any], *,
    invocation_state: dict[str, Any] | None = None,
) -> ExecutionManifestV1:
    graphs, _ = _registries()
    try:
        config = graphs[graph_id]
    except KeyError as exc:
        raise ValueError(f"unknown registered graph: {graph_id!r}") from exc
    return prepare_execution_manifest(
        config, task, context, invocation_state=invocation_state,
        origin_kind="registered",
    )


__all__ = [
    "REGISTERED_GRAPH_IDS", "prepare_execution_manifest",
    "prepare_registered_execution_manifest",
]
