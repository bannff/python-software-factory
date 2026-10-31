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


__all__ = ["AGENT_ID_ENV", "DEFAULT_AGENT_ID", "resolve_agent_config"]
