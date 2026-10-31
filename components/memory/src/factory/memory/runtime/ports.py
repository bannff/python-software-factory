"""Protocol interfaces for memory backends.

Ports define what capabilities the memory brick needs, not how they're implemented.
Adapters plug in specific backends (in-memory, Mem0, AgentCore, Redis).
"""

from __future__ import annotations

from typing import Any, Protocol

from factory.memory.runtime.models import Memory, MemoryHealth, MemoryQuery, MemoryStats


class MemoryStore(Protocol):
    """Port: Memory storage and retrieval backend."""

    def store(
        self,
        user_id: str,
        content: str,
        memory_type: str = "short_term",
        category: str = "custom",
        metadata: dict[str, Any] | None = None,
        ttl_seconds: int | None = None,
    ) -> Memory:
        """Store a new memory. Returns the created Memory."""
        ...

    def retrieve(self, query: MemoryQuery) -> list[Memory]:
        """Retrieve memories matching the query with relevance scoring."""
        ...

    def get(self, memory_id: str) -> Memory | None:
        """Get a specific memory by ID."""
        ...

    def list_all(self, user_id: str, limit: int = 100) -> list[Memory]:
        """List all memories for a user."""
        ...

    def delete(self, memory_id: str) -> bool:
        """Delete a memory. Returns True if deleted."""
        ...

    def delete_user_memories(self, user_id: str) -> int:
        """Delete all memories for a user. Returns count deleted."""
        ...

    def consolidate(self, user_id: str) -> int:
        """Consolidate short-term memories to long-term. Returns count consolidated."""
        ...

    def stats(self, user_id: str | None = None) -> MemoryStats:
        """Get memory statistics, optionally filtered by user."""
        ...

    def health_check(self) -> MemoryHealth:
        """Check backend health."""
        ...
