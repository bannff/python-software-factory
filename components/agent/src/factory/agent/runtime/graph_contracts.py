"""Typed graph and swarm registry contracts."""
from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

_READ_ONLY_TOOLS = frozenset({
    "dataset_get_capabilities", "dataset_describe_config_schema",
    "dataset_get_job", "dataset_get_artifact", "dataset_resolve_artifact",
    "devtools_read_file", "devtools_list_dir", "devtools_search",
    "devtools_git_status", "devtools_git_diff", "devtools_git_log",
})


def is_read_only_tool(name: str) -> bool:
    """Resolve against a closed, repository-owned read-only tool registry."""
    return name.replace(".", "_") in _READ_ONLY_TOOLS


class AgentNodeRef(BaseModel):
    """Graph node backed by a persona with explicit node-over-persona overrides."""

    id: str
    type: Literal["agent"]
    agent_id: str | None = None
    description: str = ""
    system_prompt: str | None = None
    model: str | None = None
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    context: dict[str, Any] | None = None
    mcp_tool_allowlist: list[str] | None = None
    read_only: bool = False
    output_schema: str | None = None
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _read_only_tools_are_closed(self) -> "AgentNodeRef":
        if not self.read_only:
            return self
        if self.mcp_tool_allowlist is None:
            raise ValueError("read_only nodes require an explicit mcp_tool_allowlist")
        invalid = [t for t in self.mcp_tool_allowlist if not is_read_only_tool(t)]
        if invalid:
            raise ValueError(f"read_only node contains mutating/unknown tools: {invalid}")
        return self


class SwarmNodeRef(BaseModel):
    id: str
    type: Literal["swarm"]
    swarm_id: str
    description: str = ""
    model_config = ConfigDict(extra="forbid")


class GraphNodeRef(BaseModel):
    id: str
    type: Literal["graph"]
    graph_id: str
    description: str = ""
    model_config = ConfigDict(extra="forbid")


class CustomNodeRef(BaseModel):
    id: str
    type: Literal["custom"]
    class_name: str = Field(alias="class")
    config: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


NodeRef = Annotated[
    Union[AgentNodeRef, SwarmNodeRef, GraphNodeRef, CustomNodeRef],
    Field(discriminator="type"),
]
NodeConfig = NodeRef


class EdgeConfig(BaseModel):
    source: str
    target: str
    condition: str | None = None
    model_config = ConfigDict(extra="forbid")


class SwarmAgentConfig(BaseModel):
    id: str
    name: str = ""
    model: str
    system_prompt: str
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    description: str = ""
    model_config = ConfigDict(extra="forbid")


class GraphConfig(BaseModel):
    id: str
    kind: Literal["graph"] = "graph"
    name: str
    description: str = ""
    nodes: list[NodeRef] = Field(default_factory=list)
    edges: list[EdgeConfig] = Field(default_factory=list)
    entry_points: list[str] = Field(default_factory=list)
    entry_point: str | None = None
    terminal_node: str | None = None
    max_node_executions: int | None = None
    max_cycles: int | None = None
    execution_timeout: float = 1800.0
    node_timeout: float = 300.0
    required_bricks: list[str] = Field(default_factory=list)
    context_vars: list[str] = Field(default_factory=list)
    conditions: dict[str, str] = Field(default_factory=dict)
    tool_allowlist: list[str] | None = None
    resumable: bool = False
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_execution_contract(self) -> "GraphConfig":
        if self.entry_point and self.entry_points and self.entry_point not in self.entry_points:
            raise ValueError("entry_point and entry_points disagree")
        for name, value in (("execution_timeout", self.execution_timeout),
                            ("node_timeout", self.node_timeout)):
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.max_node_executions is not None and self.max_node_executions <= 0:
            raise ValueError("max_node_executions must be positive")
        if self.max_cycles is not None and self.max_cycles < 1:
            raise ValueError("max_cycles must be >= 1")
        node_ids = [node.id for node in self.nodes]
        unique_ids = set(node_ids)
        if len(unique_ids) != len(node_ids):
            raise ValueError("graph node ids must be unique")
        for edge in self.edges:
            if edge.source not in unique_ids or edge.target not in unique_ids:
                raise ValueError(
                    f"edge {edge.source!r}->{edge.target!r} references an unknown node"
                )
        entries = set(self.entry_points)
        if self.entry_point:
            entries.add(self.entry_point)
        unknown_entries = entries - unique_ids
        if unknown_entries:
            raise ValueError(
                f"entry points reference unknown nodes: {sorted(unknown_entries)}"
            )
        if self.terminal_node and self.terminal_node not in unique_ids:
            raise ValueError(f"terminal_node {self.terminal_node!r} is unknown")
        return self


class SwarmConfig(BaseModel):
    id: str
    kind: Literal["swarm"] = "swarm"
    name: str
    description: str = ""
    entry_point: str
    agents: list[SwarmAgentConfig] = Field(default_factory=list)
    max_handoffs: int = 20
    max_iterations: int = 20
    execution_timeout: float = 900.0
    node_timeout: float = 300.0
    required_bricks: list[str] = Field(default_factory=list)
    context_vars: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    repetitive_handoff_detection_window: int = 8
    repetitive_handoff_min_unique_agents: int = 3
    model_config = ConfigDict(extra="forbid")


__all__ = [
    "AgentNodeRef", "CustomNodeRef", "EdgeConfig", "GraphConfig",
    "GraphNodeRef", "NodeConfig", "NodeRef", "SwarmAgentConfig",
    "SwarmConfig", "SwarmNodeRef", "is_read_only_tool",
]
