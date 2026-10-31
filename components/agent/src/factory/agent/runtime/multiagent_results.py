"""Result dataclasses for multi-agent executions.

Extracted from ``ports.py`` (bd-qev3) to keep that file under 200 LOC
once ``run_id`` was added for chat-tool-result correlation. The same
extraction pattern as ``chat_port.py``: ``ports.py`` re-exports
``SwarmResult`` / ``GraphResult`` for back-compat with existing
``from factory.agent.runtime.ports import SwarmResult, GraphResult``
callers (executors, adapters, tests).

``run_id`` defaults to ``""`` so all existing constructions remain
valid; the executor mutates the field post-invoke inside
``envelope_scope`` (Option A from the meta-architect verdict
``13b76747``) so the SDK ``SwarmRuntime`` / ``GraphRuntime`` Protocol
boundary stays unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .ports import NodeExecution


@dataclass
class SwarmResult:
    """Result from a swarm execution. Preserves rich SwarmNode data."""

    status: str
    output: str
    node_history: list[NodeExecution] = field(default_factory=list)
    execution_time: float = 0.0
    accumulated_usage: dict[str, int] = field(default_factory=dict)
    accumulated_metrics: dict[str, Any] = field(default_factory=dict)
    execution_count: int = 0
    per_node_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    run_id: str = ""

    @property
    def node_ids(self) -> list[str]:
        """Convenience: list of node_id strings for backward compat."""
        return [n.node_id for n in self.node_history]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "output": self.output,
            "node_history": [
                {"node_id": n.node_id, "status": n.status,
                 "usage": n.usage, "metrics_summary": n.metrics_summary}
                for n in self.node_history
            ],
            "execution_time": self.execution_time,
            "accumulated_usage": self.accumulated_usage,
            "accumulated_metrics": self.accumulated_metrics,
            "execution_count": self.execution_count,
            "per_node_results": self.per_node_results,
            "run_id": self.run_id,
        }


@dataclass
class GraphResult:
    """Result from a graph execution."""

    status: str
    execution_order: list[str] = field(default_factory=list)
    results: dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    node_errors: dict[str, str] = field(default_factory=dict)
    node_statuses: dict[str, str] = field(default_factory=dict)
    structured_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    session_id: str = ""
    cached: bool = False
    run_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "execution_order": self.execution_order,
            "results": self.results,
            "execution_time": self.execution_time,
            "node_errors": self.node_errors,
            "node_statuses": self.node_statuses,
            "structured_outputs": self.structured_outputs,
            "session_id": self.session_id,
            "cached": self.cached,
            "run_id": self.run_id,
        }
