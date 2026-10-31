"""Ambient authority for Artifacts MCP."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import get_envelope


def authority() -> tuple[str, str, str]:
    context = get_envelope()
    if not isinstance(context, dict):
        raise ValueError("artifact_owner_context_required")
    tenant = context.get("tenant_id")
    owner = context.get("principal_id")
    if not all(isinstance(item, str) and item for item in (tenant, owner)):
        raise ValueError("artifact_owner_context_required")
    actor = "agent" if isinstance(context.get("agent_id"), str) else "human"
    return tenant, owner, actor


__all__ = ["authority"]
