"""Operational-modality trait for MCP tools."""
from __future__ import annotations

from typing import Any, Callable

OP_KINDS: frozenset[str] = frozenset({"shell", "read", "write", "authoring"})


def op_kind(kind: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Tag a tool with its closed-set operational modality."""
    if kind not in OP_KINDS:
        raise ValueError(f"op_kind must be one of {sorted(OP_KINDS)}, got {kind!r}")

    def decorate(func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(func, "_mcp_op_kind", kind)
        return func

    return decorate
