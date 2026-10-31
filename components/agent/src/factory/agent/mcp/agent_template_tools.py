"""Typed persona (agent template) MCP tools, gated per action.

Split out of ``mcp/authoring.py`` so each persona action carries its own
gate (create / delete / fork / reset) without pushing that module over the
LOC ceiling.
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, authoring

from ..authoring import (
    AuthoringError, AuthoringManager, AuthoringRootUnavailable, config_root_for,
    gated_tool, policy_for,
)
from .authoring import authoring_result, root_unavailable
from .contracts.authoring import (
    AgentCreateInput, AgentDeleteInput, AgentForkInput, AuthoringResult,
)

if TYPE_CHECKING:
    from ..agent import SuperAgent


def register(mcp: Any, agent: "SuperAgent") -> None:
    """Register persona create/delete/fork/reset behind their own gates."""
    manager = AuthoringManager(config_root_for(agent))
    policy = policy_for(agent)

    @gated_tool(mcp, policy, "agent_templates", "create")
    @authoring(input_model=AgentCreateInput, output_model=AuthoringResult)
    async def agent_create_agent(config: dict[str, Any]) -> ToolResult[AuthoringResult]:
        from ..registry.defaults import AGENTS_TYPED
        requested_id = str(config.get("id", ""))
        if requested_id in {entry.id for entry in AGENTS_TYPED}:
            return authoring_result({"ok": False, "error": "id_collides_with_builtin", "details": f"'{requested_id}' is a built-in persona id; choose a different id."})
        try:
            result = manager.write_yaml_config("agent", config)
        except AuthoringError as error:
            return authoring_result({"ok": False, "error": "invalid_config", "details": str(error)})
        except AuthoringRootUnavailable as error:
            return root_unavailable(error)
        await agent.agent_registry.load()
        return authoring_result({"ok": True, "id": result["id"], "path": result["path"]})

    @gated_tool(mcp, policy, "agent_templates", "delete")
    @authoring(input_model=AgentDeleteInput, output_model=AuthoringResult)
    async def agent_delete_agent(agent_id: str) -> ToolResult[AuthoringResult]:
        from ..registry.defaults import AGENTS_TYPED
        if agent_id in {entry.id for entry in AGENTS_TYPED}:
            return authoring_result({"ok": False, "error": "cannot_delete_builtin", "id": agent_id})
        removed = manager.delete_yaml_config("agent", agent_id).get("ok", False)
        await agent.agent_registry.load()
        return authoring_result({"ok": bool(removed), "error": None if removed else "not_found", "id": agent_id})

    @gated_tool(mcp, policy, "agent_templates", "fork")
    @authoring(input_model=AgentForkInput, output_model=AuthoringResult)
    async def agent_fork_agent(source_agent_id: str, new_agent_id: str) -> ToolResult[AuthoringResult]:
        """Copy any persona (built-in or user) to a new id the owner can
        freely edit. Built-ins always win an id collision (registry
        invariant), so a fork is always a distinct id, never an override —
        row 33 (feature-map): "the definition panel forks a private
        template copy on first edit"."""
        source = agent.agent_registry.get(source_agent_id)
        if source is None:
            return authoring_result({"ok": False, "error": "source_not_found", "id": source_agent_id})
        from ..registry.defaults import AGENTS_TYPED
        if new_agent_id in {entry.id for entry in AGENTS_TYPED}:
            return authoring_result({"ok": False, "error": "id_collides_with_builtin",
                                     "details": f"'{new_agent_id}' is a built-in persona id; choose a different id."})
        config = {**source.model_dump(), "id": new_agent_id}
        try:
            result = manager.write_yaml_config("agent", config)
        except AuthoringError as error:
            return authoring_result({"ok": False, "error": "invalid_config", "details": str(error)})
        except AuthoringRootUnavailable as error:
            return root_unavailable(error)
        manager.write_fork_provenance("agent", new_agent_id, source_agent_id)
        await agent.agent_registry.load()
        return authoring_result({"ok": True, "id": result["id"], "path": result["path"], "forked_from": source_agent_id})

    @gated_tool(mcp, policy, "agent_templates", "reset")
    @authoring(input_model=AgentDeleteInput, output_model=AuthoringResult)
    async def agent_reset_agent(agent_id: str) -> ToolResult[AuthoringResult]:
        """Discard a fork's local edits, restoring it to its source
        persona's CURRENT definition (built-ins may themselves change
        between releases; reset always re-copies from the live source,
        never a frozen snapshot). Only valid for a persona this tool
        itself forked — a plain user-authored persona with no recorded
        provenance has nothing to reset to."""
        source_id = manager.read_fork_provenance("agent", agent_id)
        if source_id is None:
            return authoring_result({"ok": False, "error": "not_a_fork", "id": agent_id})
        source = agent.agent_registry.get(source_id)
        if source is None:
            return authoring_result({"ok": False, "error": "source_not_found", "id": source_id})
        config = {**source.model_dump(), "id": agent_id}
        try:
            manager.write_yaml_config("agent", config)
        except AuthoringError as error:
            return authoring_result({"ok": False, "error": "invalid_config", "details": str(error)})
        except AuthoringRootUnavailable as error:
            return root_unavailable(error)
        manager.write_fork_provenance("agent", agent_id, source_id)
        await agent.agent_registry.load()
        return authoring_result({"ok": True, "id": agent_id, "reset_from": source_id})


__all__ = ["register"]
