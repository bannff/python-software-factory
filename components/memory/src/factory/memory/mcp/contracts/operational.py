"""DTOs for category-neutral Memory operational MCP tools."""
from __future__ import annotations

from pydantic import Field, JsonValue

from .base import DTO, MemoryData


class MemoryStoreInput(DTO):
    content: str
    user_id: str | None = None
    memory_type: str = "short_term"
    category: str = "custom"
    metadata: dict[str, JsonValue] | None = None
    ttl_seconds: int | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=256)


class MemoryStoreOutput(DTO):
    stored: bool
    memory: MemoryData | None = None
    error: str | None = None


class MemoryRetrieveInput(DTO):
    query: str
    user_id: str | None = None
    memory_type: str | None = None
    category: str | None = None
    min_relevance: float = 0.3
    limit: int = 5
    tags: list[str] | None = None
    metadata: dict[str, str] | None = None


class MemoryRetrieveOutput(DTO):
    memories: list[MemoryData] = Field(default_factory=list)
    count: int = 0
    error: str | None = None


class MemoryDeleteOutput(DTO):
    memory_id: str
    deleted: bool


class MemoryBulkFilterInput(DTO):
    """Shared filter shape for bulk preview and delete — the SAME filter,
    so a preview's count can never drift from what apply actually removes."""
    user_id: str | None = None
    query: str | None = None
    memory_type: str | None = None
    metadata: dict[str, str] | None = None
    limit: int = Field(default=1000, ge=1, le=10_000)


class MemoryBulkPreviewOutput(DTO):
    user_id: str | None = None
    matched_count: int = 0
    sample: list[MemoryData] = Field(default_factory=list)
    error: str | None = None


class MemoryBulkDeleteOutput(DTO):
    user_id: str | None = None
    deleted_count: int = 0
    deleted_ids: list[str] = Field(default_factory=list)
    error: str | None = None


class MemoryUpdateInput(DTO):
    memory_id: str
    content: str = Field(min_length=1)


class MemoryUpdateOutput(DTO):
    memory_id: str
    updated: bool
    memory: MemoryData | None = None
    error: str | None = None


class UserInput(DTO):
    user_id: str | None = None


class DeleteUserOutput(DTO):
    user_id: str | None = None
    deleted_count: int = 0
    error: str | None = None


class ConsolidateOutput(DTO):
    user_id: str | None = None
    consolidated_count: int = 0
    error: str | None = None


class MemoryEvolveInput(UserInput):
    memory_ids: list[str] | None = None


class EvolutionDetail(DTO):
    memory_id: str
    status: str
    keywords: list[str] = Field(default_factory=list)
    error: str | None = None


class MemoryEvolveOutput(DTO):
    evolved_count: int = 0
    failed_count: int = 0
    details: list[EvolutionDetail] = Field(default_factory=list)
    error: str | None = None
