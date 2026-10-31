"""Operational MCP tools for portable graph mutations."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any

from .operational_core import register as register_core
from .provenance import register as register_provenance
from .projection import register as register_projection
from .backup import register as register_backup

if TYPE_CHECKING:
    from ..runtime.runtime import GraphRuntime


def register(mcp: Any, get_runtime: Callable[[], "GraphRuntime"]) -> None:
    """Register portable graph mutations under canonical names."""
    register_core(mcp, get_runtime)
    register_provenance(mcp, get_runtime)
    register_projection(mcp, get_runtime)
    register_backup(mcp, get_runtime)
