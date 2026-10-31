"""Core types and constants for memory brick."""

from __future__ import annotations

from enum import Enum
from typing import Literal

SCHEMA_VERSION = 1

MemoryType = Literal["short_term", "long_term", "episodic"]
BackendType = Literal["memory", "mem0", "agentcore", "zep", "cognee", "neo4j", "amem", "graph"]


class MemoryCategory(str, Enum):
    """Categories for memory classification."""

    PREFERENCE = "preference"
    FACT = "fact"
    SUMMARY = "summary"
    CONTEXT = "context"
    CUSTOM = "custom"
