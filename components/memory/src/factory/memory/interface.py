"""Polylith interface for memory brick."""

from factory.memory.runtime.partition import (
    derive_memory_user_id,
    validate_memory_scope,
    validate_owner_id,
)
from factory.memory.runtime.runtime import MemoryRuntime as Runtime
from factory.memory.server import create_mcp_server as create_server

__all__ = [
    "Runtime",
    "create_server",
    "derive_memory_user_id",
    "validate_memory_scope",
    "validate_owner_id",
]
