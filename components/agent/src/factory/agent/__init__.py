"""Agent brick with lazy legacy exports during the Lang runtime cutover."""

from __future__ import annotations

from typing import Any

__all__ = ["SuperAgent", "CustomNode", "tool"]
__version__ = "0.1.0"


def __getattr__(name: str) -> Any:
    """Avoid importing the legacy Strands/FastMCP runtime for Lang adapters."""
    if name == "SuperAgent":
        from factory.agent.agent import SuperAgent
        return SuperAgent
    if name == "CustomNode":
        from factory.agent.nodes.base import CustomNode
        return CustomNode
    if name == "tool":
        from factory.agent.registry.tools import tool
        return tool
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
