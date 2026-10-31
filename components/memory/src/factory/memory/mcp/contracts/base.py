"""Shared strict transport DTOs for Memory MCP tools."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, JsonValue


class DTO(BaseModel):
    """Same-brick strict public MCP transport contract."""

    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(DTO):
    """Strict empty input for parameterless tools."""


class MemoryData(DTO):
    """JSON-safe representation of a memory record."""

    id: str
    user_id: str
    content: str
    memory_type: str
    category: str
    metadata: dict[str, JsonValue]
    relevance_score: float
    created_at: str
    updated_at: str | None = None
    expires_at: str | None = None
