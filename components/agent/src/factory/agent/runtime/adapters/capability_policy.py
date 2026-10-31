"""Persona capability narrowing over trusted MCP gateway authority."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import CapabilityScope

_MAX_DELEGATION_DEPTH = 2
_SPAWN_PREFIX = "agent_spawn_"


def effective_persona_scope(
    base: CapabilityScope, persona: Any,
) -> CapabilityScope:
    """Derive one immutable persona scope without adding parent authority."""
    if persona.exact_tools:
        from factory.agent.runtime.execution_manifest.preparation_support import (
            partition_tools,
        )
        _local, requested = partition_tools(list(persona.tools))
        from factory.mcp_server.interface import resolve_public_mcp_names
        canonical = resolve_public_mcp_names(requested)
        names = base.tool_names.intersection(canonical)
        if base.delegation_depth >= _MAX_DELEGATION_DEPTH:
            names = frozenset(name for name in names if not _is_spawn(name))
    elif base.delegation_depth == 0:
        names = base.tool_names
    else:
        names = frozenset(name for name in base.tool_names if not _is_spawn(name))
    return CapabilityScope.create(
        base.policy_id, names, delegation_depth=base.delegation_depth,
    )


def delegation_allowed(scope: CapabilityScope) -> bool:
    """Return whether another bounded child may be created from ``scope``."""
    return scope.delegation_depth < _MAX_DELEGATION_DEPTH


def _is_spawn(name: str) -> bool:
    return name.startswith(_SPAWN_PREFIX)


__all__ = ["delegation_allowed", "effective_persona_scope"]
