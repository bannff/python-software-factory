"""Framework-neutral persona selection for Agent runtime adapters."""
from __future__ import annotations

from typing import Any

DEFAULT_AGENT_ID = "companion-x-default"
AGENT_ID_ENV = "COMPANION_X_CHAT_AGENT_ID"


def resolve_agent_config(agent_id: str) -> Any:
    """Resolve one built-in or user-authored persona, failing loudly on miss."""
    from factory.agent.registry.unified import unified_personas

    personas = unified_personas()
    for config in personas:
        if config.id == agent_id:
            return config
    known = sorted({config.id for config in personas})
    raise ValueError(
        f"{AGENT_ID_ENV}={agent_id!r} does not resolve to a registered agent. "
        f"Known ids: {known}"
    )


def resolve_persona(agent_id: str, member: Any | None = None) -> Any:
    """Resolve a registered persona, or build one from an inline member.

    A member is an exact-tools persona (as ``compile_swarm`` freezes it): its
    MCP tools are its whole scope; naming none keeps the inherited scope.
    """
    if member is None:
        return resolve_agent_config(agent_id)
    from .agent_contracts import AgentConfig
    from .execution_manifest.preparation_support import partition_tools

    _local, mcp = partition_tools(list(member.tools))
    return AgentConfig(
        id=agent_id, name=agent_id, model=member.model,
        system_prompt=member.system_prompt, tools=list(member.tools),
        exact_tools=bool(mcp),
    )


__all__ = [
    "AGENT_ID_ENV", "DEFAULT_AGENT_ID", "resolve_agent_config", "resolve_persona",
]
