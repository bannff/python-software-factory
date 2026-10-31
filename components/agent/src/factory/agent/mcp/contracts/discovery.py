"""Contracts for Agent discovery and read-only MCP tools."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictDTO(BaseModel):
    """Shared strict same-brick contract base."""

    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(StrictDTO):
    """Flat zero-argument MCP input."""


class AgentSummary(StrictDTO):
    id: str
    name: str
    description: str = ""
    model: str


class SwarmAgentSummary(StrictDTO):
    id: str
    name: str


class SwarmSummary(StrictDTO):
    id: str
    name: str
    description: str = ""
    entry_point: str
    agents: list[SwarmAgentSummary]
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None


class GraphNode(StrictDTO):
    id: str
    type: str


class GraphEdge(StrictDTO):
    source: str
    target: str


class GraphSummary(StrictDTO):
    id: str
    name: str
    description: str = ""
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    entry_points: list[str]


class ToolParameter(StrictDTO):
    name: str
    type: str
    default: Any = None


class ToolSummary(StrictDTO):
    name: str
    description: str
    parameters: list[ToolParameter]


class CapabilitiesOutput(StrictDTO):
    deterministic_tools: list[ToolSummary]
    swarms: list[dict[str, Any]]
    graphs: list[dict[str, Any]]
    agents: list[AgentSummary]


class AgentRegistryOutput(StrictDTO):
    count: int
    agents: list[AgentSummary]


class SwarmRegistryOutput(StrictDTO):
    count: int
    swarms: list[SwarmSummary]


class GraphRegistryOutput(StrictDTO):
    count: int
    graphs: list[GraphSummary]


class HealthOutput(StrictDTO):
    status: str
    config_dir: str
    agents_loaded: int
    swarms_loaded: int
    graphs_loaded: int
    squads_loaded: int


class WorkflowStatusInput(StrictDTO):
    workflow_id: str


class WorkflowStatusOutput(StrictDTO):
    found: bool
    workflow_id: str
    state: dict[str, Any] | None = None


class SkillSummary(StrictDTO):
    id: str
    name: str
    description: str = ""


class SkillIdInput(StrictDTO):
    skill_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")


class SkillAddInput(SkillIdInput):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    body: str = Field(min_length=1, max_length=100_000)

    @field_validator("name", "body")
    @classmethod
    def required_text(cls, value: str) -> str:
        if "\x00" in value or not value.strip():
            raise ValueError("skill text must be nonblank and cannot contain NUL")
        return value

    @field_validator("description")
    @classmethod
    def safe_description(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("skill text cannot contain NUL")
        return value


class SkillsOutput(StrictDTO):
    count: int
    skills: list[SkillSummary]


class SkillDetailOutput(SkillSummary):
    body: str


class SkillAddOutput(StrictDTO):
    created: bool
    skill: SkillSummary


class SkillDeleteOutput(StrictDTO):
    deleted: bool
    skill_id: str


class ViewsOutput(StrictDTO):
    views: list[dict[str, Any]]
