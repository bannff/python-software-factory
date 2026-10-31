"""DTOs for Storage graph MCP tools."""
from __future__ import annotations

from pydantic import Field, JsonValue

from .base import DTO, EdgeData, JsonObject, NodeData


class GraphAddNodeInput(DTO):
    labels: list[str]
    properties: JsonObject | None = None


class GraphNodeOutput(DTO):
    found: bool = True
    id: str = ""
    labels: list[str] = Field(default_factory=list)
    properties: JsonObject = Field(default_factory=dict)
    node_id: str = ""
    error: str | None = None


class GraphGetNodeInput(DTO):
    node_id: str


class GraphUpdateNodeInput(DTO):
    node_id: str
    properties: JsonObject


class GraphDeleteNodeInput(DTO):
    node_id: str


class GraphDeleteNodeOutput(DTO):
    deleted: bool
    node_id: str


class GraphAddEdgeInput(DTO):
    source_id: str
    target_id: str
    edge_type: str
    properties: JsonObject | None = None


class GraphEdgeOutput(EdgeData):
    pass


class GraphGetEdgesInput(DTO):
    node_id: str
    direction: str = "both"


class GraphGetEdgesOutput(DTO):
    edges: list[EdgeData]
    count: int


class GraphDeleteEdgeInput(DTO):
    edge_id: str


class GraphDeleteEdgeOutput(DTO):
    deleted: bool
    edge_id: str


class GraphQueryInput(DTO):
    cypher: str
    params: JsonObject | None = None


class GraphQueryOutput(DTO):
    nodes: list[NodeData]
    edges: list[EdgeData]
    raw: JsonValue | None = None
