"""DTOs for Memory's Neo4j-backed search and maintenance MCP tools."""
from __future__ import annotations

from pydantic import Field, JsonValue

from .base import DTO, MemoryData


class HybridSearchInput(DTO):
    user_id: str
    query: str | None = None
    anchor_memory_id: str | None = None
    limit: int = 10
    semantic_weight: float = 0.5
    structural_weight: float = 0.3
    traversal_weight: float = 0.2


class HybridResult(DTO):
    memory: MemoryData
    combined_score: float
    semantic_score: float
    structural_score: float
    traversal_score: float


class HybridSearchOutput(DTO):
    available: bool
    results: list[HybridResult] = Field(default_factory=list)
    count: int = 0
    error: str | None = None


class EmbedBackfillInput(DTO):
    user_id: str
    limit: int = 100


class EmbedBackfillOutput(DTO):
    available: bool
    user_id: str
    embedded: int = 0
    total_checked: int = 0
    error: str | None = None


class SearchByTimeInput(DTO):
    user_id: str | None = None
    time_from: str | None = None
    time_to: str | None = None
    query: str | None = None
    limit: int = 20


class SearchByTimeOutput(DTO):
    available: bool
    results: list[MemoryData] = Field(default_factory=list)
    count: int = 0
    error: str | None = None


class ViewsOutput(DTO):
    views: list[dict[str, JsonValue]]
