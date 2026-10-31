"""Strict typed authoring MCP tools for SuperAgent."""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING, cast

from factory.mcp_utils.interface import ToolResult, authoring, ok

from ..authoring import (
    AuthoringError, AuthoringManager, AuthoringPolicy, AuthoringRootUnavailable, ConfigKind,
    config_root_for, gated_tool, policy_for, settings_authoring_enabled,
)
from .contracts.authoring import (
    AuthoringResult, AuthoringStatusOutput, ConfigItemInput, ConfigWriteInput, KindInput,
    ModuleInput, ModuleWriteInput, SettingsWriteInput, SquadCreateInput, SquadDeleteInput,
)
from .contracts.discovery import EmptyInput

if TYPE_CHECKING:
    from ..agent import SuperAgent


def authoring_result(value: dict[str, Any]) -> ToolResult[AuthoringResult]:
    """Keep existing authoring payloads opaque under one concrete DTO."""
    return ok(AuthoringResult(success=bool(value.get("ok", True)), result=value))


def root_unavailable(error: AuthoringRootUnavailable) -> ToolResult[AuthoringResult]:
    """Report an unusable authoring root, naming the variable and the path."""
    return authoring_result({
        "ok": False, "error": "authoring_root_unavailable", "details": str(error),
    })


def authoring_write(operation: Callable[[], dict[str, Any]]) -> ToolResult[AuthoringResult]:
    """Run one authoring write, typing an unusable root instead of a raw OSError."""
    try:
        return authoring_result(operation())
    except AuthoringRootUnavailable as error:
        return root_unavailable(error)


def _surface_gate(kind: str, action: str) -> tuple[str, str]:
    """The (surface, action) pair that gates authoring this config kind.

    Personas live on their own surface; every other kind (swarm, graph,
    squad, settings, tool) is generic config content.
    """
    return ("agent_templates", action) if kind == "agent" else ("config", "write")


def _denied_surface(policy: AuthoringPolicy, kind: str, action: str) -> str | None:
    """Surface denying this (kind, action), or ``None`` when it is allowed."""
    surface, required = _surface_gate(kind, action)
    return None if policy.allows(surface, required) else surface


def _surface_denied(surface: str) -> dict[str, Any]:
    return {"ok": False, "error": "authoring_disabled_for_surface", "details": surface}


def register(mcp: Any, agent: "SuperAgent") -> None:
    """Register per-surface gated configuration authoring tools."""
    manager = AuthoringManager(config_root_for(agent))
    policy = policy_for(agent)

    @mcp.tool()
    @authoring(input_model=EmptyInput, output_model=AuthoringStatusOutput)
    def authoring_status() -> ToolResult[AuthoringStatusOutput]:
        """Report whether any authoring surface is open; see agent_authoring_capabilities."""
        return ok(AuthoringStatusOutput(
            enabled=policy.any_allowed(), config_root=str(config_root_for(agent)),
        ))

    # Reads ------------------------------------------------------------
    @gated_tool(mcp, policy, "config", "read")
    @authoring(input_model=KindInput, output_model=AuthoringResult)
    def list_config_items(kind: str) -> ToolResult[AuthoringResult]:
        return authoring_result({"ok": True, "items": manager.list_items(cast(ConfigKind, kind))})

    @gated_tool(mcp, policy, "config", "read")
    @authoring(input_model=ConfigItemInput, output_model=AuthoringResult)
    def read_config(kind: str, item_id: str) -> ToolResult[AuthoringResult]:
        return authoring_result({"ok": True, "config": manager.read_yaml_config(cast(ConfigKind, kind), item_id)})

    @gated_tool(mcp, policy, "config", "read")
    @authoring(input_model=EmptyInput, output_model=AuthoringResult)
    def read_settings() -> ToolResult[AuthoringResult]:
        return authoring_result({"ok": True, "settings": manager.read_settings()})

    @gated_tool(mcp, policy, "config", "read")
    @authoring(input_model=ModuleInput, output_model=AuthoringResult)
    def read_tool_module(module_name: str) -> ToolResult[AuthoringResult]:
        return authoring_result(manager.read_tool_module(module_name))

    # Writes -----------------------------------------------------------
    @gated_tool(mcp, policy, "config", "write")
    @authoring(input_model=ConfigWriteInput, output_model=AuthoringResult)
    def write_config(kind: str, config: dict[str, Any]) -> ToolResult[AuthoringResult]:
        if denied := _denied_surface(policy, kind, "create"):
            return authoring_result(_surface_denied(denied))
        return authoring_write(lambda: manager.write_yaml_config(cast(ConfigKind, kind), config))

    @gated_tool(mcp, policy, "config", "write")
    @authoring(input_model=ConfigItemInput, output_model=AuthoringResult)
    def delete_config(kind: str, item_id: str) -> ToolResult[AuthoringResult]:
        if denied := _denied_surface(policy, kind, "delete"):
            return authoring_result(_surface_denied(denied))
        return authoring_result(manager.delete_yaml_config(cast(ConfigKind, kind), item_id))

    @gated_tool(mcp, policy, "config", "write")
    @authoring(input_model=SettingsWriteInput, output_model=AuthoringResult)
    def write_settings(settings: dict[str, Any]) -> ToolResult[AuthoringResult]:
        if settings_authoring_enabled(settings):
            return authoring_result({
                "ok": False, "error": "authoring_gate_immutable",
                "details": "settings.authoring.enabled may not be raised from the config "
                           "surface; set a FACTORY_AGENT_AUTHORING_* variable instead",
            })
        return authoring_write(lambda: manager.write_settings(settings))

    @gated_tool(mcp, policy, "config", "write")
    @authoring(input_model=ModuleWriteInput, output_model=AuthoringResult)
    def write_tool_module(module_name: str, code: str) -> ToolResult[AuthoringResult]:
        return authoring_write(lambda: manager.write_tool_module(module_name, code))

    @gated_tool(mcp, policy, "config", "write")
    @authoring(input_model=ModuleInput, output_model=AuthoringResult)
    def delete_tool_module(module_name: str) -> ToolResult[AuthoringResult]:
        return authoring_result(manager.delete_tool_module(module_name))

    @gated_tool(mcp, policy, "config", "write")
    @authoring(input_model=EmptyInput, output_model=AuthoringResult)
    async def reload_config() -> ToolResult[AuthoringResult]:
        await agent.agent_registry.load()
        await agent.swarm_registry.load()
        await agent.graph_registry.load()
        await agent.tool_registry.load()
        if agent.squad_registry is not None:
            await agent.squad_registry.load()
        return authoring_result({"ok": True, "agents": len(agent.agent_registry.agents)})

    @gated_tool(mcp, policy, "config", "write")
    @authoring(input_model=SquadCreateInput, output_model=AuthoringResult)
    async def agent_create_squad(config: dict[str, Any]) -> ToolResult[AuthoringResult]:
        """Create or update a deployable squad (team-of-agents) as DATA."""
        from ..registry.defaults_squads import SQUADS_TYPED
        requested_id = str(config.get("id", ""))
        if requested_id in {entry.id for entry in SQUADS_TYPED}:
            return authoring_result({"ok": False, "error": "id_collides_with_builtin",
                                    "details": f"'{requested_id}' is a built-in squad id; choose another."})
        try:
            result = manager.write_yaml_config("squad", config)
        except AuthoringError as error:
            return authoring_result({"ok": False, "error": "invalid_config", "details": str(error)})
        except AuthoringRootUnavailable as error:
            return root_unavailable(error)
        if agent.squad_registry is not None:
            await agent.squad_registry.load()
        return authoring_result({"ok": True, "id": result["id"], "path": result["path"]})

    @gated_tool(mcp, policy, "config", "write")
    @authoring(input_model=SquadDeleteInput, output_model=AuthoringResult)
    async def agent_delete_squad(squad_id: str) -> ToolResult[AuthoringResult]:
        """Delete a user-authored squad; built-in squads cannot be deleted."""
        from ..registry.defaults_squads import SQUADS_TYPED
        if squad_id in {entry.id for entry in SQUADS_TYPED}:
            return authoring_result({"ok": False, "error": "cannot_delete_builtin", "id": squad_id})
        removed = manager.delete_yaml_config("squad", squad_id).get("ok", False)
        if agent.squad_registry is not None:
            await agent.squad_registry.load()
        return authoring_result({"ok": bool(removed), "error": None if removed else "not_found", "id": squad_id})
