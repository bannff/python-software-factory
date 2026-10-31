"""Contracts for Agent authoring MCP tools."""
from __future__ import annotations

from typing import Any, Literal

from .discovery import StrictDTO

ConfigKind = Literal["agent", "swarm", "graph"]


class KindInput(StrictDTO):
    kind: ConfigKind


class ConfigItemInput(KindInput):
    item_id: str


class ConfigWriteInput(KindInput):
    config: dict[str, Any]


class SettingsWriteInput(StrictDTO):
    settings: dict[str, Any]


class ModuleInput(StrictDTO):
    module_name: str


class ModuleWriteInput(ModuleInput):
    code: str


class AgentCreateInput(StrictDTO):
    config: dict[str, Any]


class AgentDeleteInput(StrictDTO):
    agent_id: str


class AgentForkInput(StrictDTO):
    source_agent_id: str
    new_agent_id: str


class SquadCreateInput(StrictDTO):
    config: dict[str, Any]


class SquadDeleteInput(StrictDTO):
    squad_id: str


class AuthoringStatusOutput(StrictDTO):
    enabled: bool
    config_root: str


class AuthoringResult(StrictDTO):
    success: bool
    result: dict[str, Any]


class ConfigSurface(StrictDTO):
    """Per-action capability of the generic config surface."""

    read: bool = False
    write: bool = False


class LifecycleSurface(StrictDTO):
    """Per-action capability of the skills/steering/template surfaces."""

    add: bool = False
    create: bool = False
    update: bool = False
    delete: bool = False
    fork: bool = False
    reset: bool = False


class AuthoringRootInfo(StrictDTO):
    path: str
    source: Literal["env", "default"]


class RootsInfo(StrictDTO):
    config: AuthoringRootInfo
    skills: AuthoringRootInfo
    steering: AuthoringRootInfo


class AuthoringCapabilitiesOutput(StrictDTO):
    """Effective authoring capability, derived from the same policy as the gates."""

    config: ConfigSurface
    skills: LifecycleSurface
    steering: LifecycleSurface
    agent_templates: LifecycleSurface
    roots: RootsInfo
