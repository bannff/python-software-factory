"""Compile and flatten GraphConfig into replay-complete manifest nodes."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from .compile_agents import compile_agent, compile_swarm
from .compiled import CompiledEdge, CompiledGraph
from .compile_workflow import compile_workflow

_ALLOWED_CONDITIONS = {None, "all-predecessors-valid"}


def compile_config(
    config: Any, context: dict[str, Any], graph_map: dict[str, Any],
    swarm_map: dict[str, Any], prefix: str = "", stack: tuple[str, ...] = (),
) -> CompiledGraph:
    if config.id in stack:
        raise ValueError(f"recursive graph reference: {' -> '.join((*stack, config.id))}")
    if config.kind == "workflow":
        return compile_workflow(config, context, prefix)
    local_nodes = []
    local_edges: list[CompiledEdge] = []
    entries_by_id: dict[str, tuple[str, ...]] = {}
    terminals_by_id: dict[str, tuple[str, ...]] = {}
    for node in config.nodes:
        node_id = f"{prefix}{node.id}"
        if node.type == "custom":
            raise ValueError(f"custom graph node is not replayable: {node.id!r}")
        if node.type == "agent":
            materialized = compile_agent(
                node.model_copy(update={"id": node_id}), context, config.tool_allowlist,
            )
            local_nodes.append(materialized)
            entries_by_id[node.id] = terminals_by_id[node.id] = (node_id,)
        elif node.type == "swarm":
            try:
                swarm = swarm_map[node.swarm_id]
            except KeyError as exc:
                raise ValueError(f"unknown swarm reference: {node.swarm_id!r}") from exc
            local_nodes.append(compile_swarm(node_id, swarm, context))
            entries_by_id[node.id] = terminals_by_id[node.id] = (node_id,)
        elif node.type == "graph":
            try:
                child_config = graph_map[node.graph_id]
            except KeyError as exc:
                raise ValueError(f"unknown graph reference: {node.graph_id!r}") from exc
            child = compile_config(
                child_config, context, graph_map, swarm_map,
                prefix=f"{node_id}--", stack=(*stack, config.id),
            )
            local_nodes.extend(child.nodes)
            local_edges.extend(child.edges)
            entries_by_id[node.id] = child.entries
            terminals_by_id[node.id] = child.terminals
        else:
            raise ValueError(f"unknown graph node type: {node.type!r}")
    seen_pairs = {(edge.source, edge.target) for edge in local_edges}
    for edge in config.edges:
        if edge.condition not in _ALLOWED_CONDITIONS:
            raise ValueError(f"unknown graph condition: {edge.condition!r}")
        for source in terminals_by_id[edge.source]:
            for target in entries_by_id[edge.target]:
                pair = (source, target)
                if pair in seen_pairs:
                    raise ValueError(f"duplicate graph edge: {pair!r}")
                seen_pairs.add(pair)
                local_edges.append(CompiledEdge(source, target, edge.condition))
    logical_entries = list(config.entry_points)
    if config.entry_point and config.entry_point not in logical_entries:
        logical_entries.append(config.entry_point)
    if not logical_entries:
        targets = {edge.target for edge in config.edges}
        logical_entries = [node.id for node in config.nodes if node.id not in targets]
    entries = tuple(
        expanded for logical in logical_entries for expanded in entries_by_id[logical]
    )
    if not entries:
        raise ValueError("graph has no entry points")
    return CompiledGraph(
        graph_id=config.id, name=config.name, description=config.description,
        nodes=tuple(local_nodes), edges=tuple(local_edges), entries=entries,
        max_node_executions=config.max_node_executions,
        max_cycles=config.max_cycles, execution_timeout=config.execution_timeout,
        node_timeout=config.node_timeout,
    )


def freeze_edges(graph: CompiledGraph):
    from .behavior_registry import freeze_condition
    from .models import EdgeManifest

    incoming: dict[str, list[str]] = defaultdict(list)
    for edge in graph.edges:
        incoming[edge.target].append(edge.source)
    frozen = []
    for edge in graph.edges:
        predecessors = tuple(incoming[edge.target])
        name = edge.condition or (
            "all-predecessors-valid" if len(predecessors) > 1 else None
        )
        frozen.append(EdgeManifest(
            source=edge.source, target=edge.target,
            condition=freeze_condition(name, predecessors) if name else None,
            predecessors=predecessors,
        ))
    return tuple(frozen)


__all__ = ["compile_config", "freeze_edges"]
