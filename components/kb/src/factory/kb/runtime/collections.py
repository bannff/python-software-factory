"""Collection management for knowledge base."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CollectionConfig(BaseModel):
    """Configuration for a knowledge base collection."""

    id: str = Field(..., description="Unique collection identifier")
    name: str = Field(..., description="Human-readable collection name")
    description: str | None = Field(
        default=None,
        description="Collection description",
    )
    embedding_model: str = Field(
        default="default",
        description="Embedding model to use",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional collection metadata",
    )

    model_config = {"extra": "forbid"}


class CollectionStats(BaseModel):
    """Statistics for a collection."""

    collection_id: str = Field(..., description="Collection identifier")
    document_count: int = Field(default=0, description="Number of documents")
    total_size_bytes: int = Field(default=0, description="Total size in bytes")
    last_updated: str | None = Field(
        default=None,
        description="Last update timestamp",
    )

    model_config = {"extra": "forbid"}


class CollectionRegistry:
    """Registry for managing collection configurations."""

    def __init__(self) -> None:
        self._collections: dict[str, CollectionConfig] = {}

    def register(self, config: CollectionConfig) -> None:
        """Register a collection configuration."""
        self._collections[config.id] = config

    def unregister(self, collection_id: str) -> bool:
        """Unregister a collection by ID."""
        if collection_id in self._collections:
            del self._collections[collection_id]
            return True
        return False

    def get(self, collection_id: str) -> CollectionConfig | None:
        """Get a collection configuration by ID."""
        return self._collections.get(collection_id)

    def list_all(self) -> list[CollectionConfig]:
        """List all collection configurations."""
        return list(self._collections.values())

    def clear(self) -> None:
        """Clear all collections."""
        self._collections.clear()
