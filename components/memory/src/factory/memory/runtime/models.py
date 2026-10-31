"""Pydantic models for memory brick."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from factory.memory.core import SCHEMA_VERSION, BackendType, MemoryCategory

# Cypher property names CANNOT be parameterized (bd:python-factory-b2d2o,
# meta-architect verdict f279063c). Without this guard, a key like
# ``"x; MATCH (n) DETACH DELETE n; //"`` would be Cypher injection.
# Precedent: ``components/graph/.../runtime/adapters/_neo4j_finding.py::safe_label``.
_SAFE_KEY_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def safe_property_key(key: str) -> str:
    """Reject Cypher-unsafe metadata keys (bd:python-factory-b2d2o).

    Mirrors the precedent at ``graph._neo4j_finding.safe_label``. Applied
    at both the Pydantic ``field_validator`` (Q8) and on the adapter
    side (Q7) as defense-in-depth.
    """
    if not isinstance(key, str) or not _SAFE_KEY_RE.fullmatch(key):
        raise ValueError(
            f"Unsafe metadata key: {key!r} — must match {_SAFE_KEY_RE.pattern}",
        )
    return key


def _utcnow() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class Memory(BaseModel):
    """A single memory entry."""

    id: str = Field(min_length=1, max_length=128)
    user_id: str = Field(min_length=1, max_length=256)
    content: str = Field(min_length=1)
    memory_type: Literal["short_term", "long_term", "episodic"] = "short_term"
    category: MemoryCategory = MemoryCategory.CUSTOM
    metadata: dict[str, Any] = Field(default_factory=dict)
    relevance_score: float = Field(default=1.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime | None = None
    expires_at: datetime | None = None


class MemoryQuery(BaseModel):
    """Query parameters for memory retrieval."""

    user_id: str = Field(min_length=1, max_length=256)
    query: str = Field(min_length=1)
    memory_type: Literal["short_term", "long_term", "episodic"] | None = None
    category: MemoryCategory | None = None
    min_relevance: float = Field(default=0.3, ge=0.0, le=1.0)
    limit: int = Field(default=5, ge=1, le=100)
    tags: list[str] | None = Field(
        default=None,
        description=(
            "Optional metadata.tags filter (bd:python-factory-lin6p). "
            "``None`` (default) = no filter (back-compat). ``[]`` = match "
            "nothing. Non-empty list = ANY-match (intersection non-empty)."
        ),
    )
    metadata: dict[str, str] | None = Field(
        default=None,
        description=(
            "Optional metadata-attribute filter (bd:python-factory-b2d2o). "
            "AND-join across keys (all key=value pairs must match). "
            "``None`` (default) = no filter. ``{}`` ALSO = no constraints "
            "(asymmetric vs ``tags=[]`` which matches nothing — by design). "
            "Composes AND with ``tags`` filter when both set. Keys must "
            "match the Cypher-safe regex ^[a-zA-Z_][a-zA-Z0-9_]*$ to "
            "block injection on neo4j adapters (verdict f279063c)."
        ),
    )

    @field_validator("metadata")
    @classmethod
    def _validate_metadata_keys(
        cls, v: dict[str, str] | None,
    ) -> dict[str, str] | None:
        """Reject Cypher-unsafe property names at the contract boundary."""
        if v is None:
            return v
        for k in v:
            safe_property_key(k)
        return v


class MemoryHealth(BaseModel):
    """Health status for memory backend."""

    healthy: bool
    backend: str
    latency_ms: float = 0.0
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class MemoryStats(BaseModel):
    """Statistics for memory store."""

    total_memories: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    oldest_memory: datetime | None = None
    newest_memory: datetime | None = None


class AuthoringSettings(BaseModel):
    """Authoring mode settings."""

    enabled: bool = False


class Settings(BaseModel):
    """Memory brick configuration."""

    schema_version: int = Field(default=SCHEMA_VERSION)
    service_name: str = "memory-module"
    backend: BackendType = "memory"
    authoring: AuthoringSettings = Field(default_factory=AuthoringSettings)
    default_ttl_seconds: int | None = None
    max_memories_per_user: int = 1000
