"""Models for knowledge base module."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Document(BaseModel):
    """A document in the knowledge base."""

    id: str = Field(..., description="Unique document identifier")
    content: str = Field(..., description="Document content")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Document metadata",
    )
    source: str | None = Field(
        default=None,
        description="Source of the document",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp",
    )

    model_config = {"extra": "forbid"}


class SearchResult(BaseModel):
    """A search result from the knowledge base."""

    document_id: str = Field(..., description="Document identifier")
    content: str = Field(..., description="Document content or snippet")
    score: float = Field(..., description="Relevance score (0-1)")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Document metadata",
    )

    @field_validator("metadata", mode="before")
    @classmethod
    def _coerce_metadata(cls, v: Any) -> dict[str, Any]:
        return v if v is not None else {}

    model_config = {"extra": "forbid"}


class IngestResult(BaseModel):
    """Result of document ingestion."""

    document_id: str = Field(..., description="Ingested document ID")
    status: str = Field(..., description="Ingestion status")
    chunks_created: int = Field(
        default=0,
        description="Number of chunks created",
    )
    extraction_status: str | None = Field(
        default=None,
        description="Entity extraction status: success, skipped, failed, unavailable",
    )
    entities_created: int = Field(default=0, description="Entities created during extraction")
    relationships_created: int = Field(default=0, description="Relationships created during extraction")
    extraction_message: str | None = Field(default=None, description="Extraction detail message")

    model_config = {"extra": "forbid"}


class ExtractionResult(BaseModel):
    """Result of entity/relationship extraction from a document."""

    document_id: str
    entities_created: int = 0
    relationships_created: int = 0
    entity_types: list[str] = Field(default_factory=list)
    status: str = "success"  # success, skipped, error
    message: str = ""

    model_config = {"extra": "forbid"}

