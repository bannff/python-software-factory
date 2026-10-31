"""DTOs for category-neutral Memory deterministic MCP tools."""
from __future__ import annotations

from pydantic import Field, JsonValue

from .base import DTO, MemoryData


class CapabilitiesOutput(DTO):
    name: str
    version: str
    features: list[str]
    adapters: list[str]
    mcp_contract: dict[str, JsonValue]


class HealthOutput(DTO):
    healthy: bool
    backend: str
    latency_ms: float = 0.0
    message: str = ""
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ConfigSchemaOutput(DTO):
    config_schema: dict[str, JsonValue]


class MemoryIdInput(DTO):
    memory_id: str


class MemoryGetOutput(DTO):
    memory_id: str
    found: bool
    memory: MemoryData | None = None


class SimilarMemory(DTO):
    memory: MemoryData
    score: float | None = None


class RecallPathOutput(DTO):
    memory_id: str
    supported: bool
    owner_id: str | None = None
    followed: MemoryData | None = None
    similar: list[SimilarMemory] = []


class MemoryHistoryOutput(DTO):
    memory_id: str
    supported: bool
    versions: list[MemoryData] = []


class MemoryListInput(DTO):
    user_id: str | None = None
    limit: int = 100
    metadata: dict[str, str] | None = None


class MemoryListOutput(DTO):
    user_id: str
    memories: list[MemoryData]
    count: int
    error: str | None = None


class MemoryStatsInput(DTO):
    user_id: str | None = None


class MemoryStatsOutput(DTO):
    total_memories: int
    by_type: dict[str, int]
    by_category: dict[str, int]
    oldest_memory: str | None = None
    newest_memory: str | None = None


class EmbeddingStatusOutput(DTO):
    """Row 50 (Embeddings) — honest config-time status, mirrors browser's
    ``get_engine_status``: no live toggle exists (backend + embedder are
    both resolved once at process start via ``get_infra``), so this reports
    the truth and tells the operator which env var to change + restart."""
    backend: str
    is_graph_backend: bool
    embedder_configured: bool
    is_semantic: bool
    load_error: str | None = None
    model_path: str
    dimensions: int
    change_hint: str
