"""MCP primitives for memory brick."""

from factory.memory.mcp.deterministic import register as register_deterministic
from factory.memory.mcp.operational import register as register_operational
from factory.memory.mcp.hybrid_tools import register as register_hybrid
from factory.memory.mcp.temporal_tools import register as register_temporal
from factory.memory.mcp.resources import register as register_resources
from factory.memory.mcp.prompts import register as register_prompts
from factory.memory.mcp.migration_import import register as register_migration_import
from .views import register as register_views

__all__ = [
    "register_deterministic",
    "register_operational",
    "register_hybrid",
    "register_temporal",
    "register_resources",
    "register_prompts",
    "register_migration_import",
    "register_views",
]
