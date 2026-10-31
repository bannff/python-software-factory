"""Always-registered capability probe for the Agent authoring surfaces.

The probe answers from the SAME ``AuthoringPolicy`` instance the gates use,
so the booleans a UI reads can never disagree with which tools were
registered (absence and the probe agree by construction).
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from factory.mcp_utils.interface import ToolResult, deterministic, ok

from ..authoring import AuthoringPolicy, config_root_for, policy_for, resolve_root
from .contracts.authoring import (
    AuthoringCapabilitiesOutput, AuthoringRootInfo, ConfigSurface, LifecycleSurface, RootsInfo,
)
from .contracts.discovery import EmptyInput

if TYPE_CHECKING:
    from ..agent import SuperAgent

_LIFECYCLE_ACTIONS = ("add", "create", "update", "delete", "fork", "reset")


def _lifecycle(policy: AuthoringPolicy, surface: str) -> LifecycleSurface:
    return LifecycleSurface(**{
        action: policy.allows(surface, action) for action in _LIFECYCLE_ACTIONS
    })


def _root(kind: str) -> AuthoringRootInfo:
    root = resolve_root(kind)
    return AuthoringRootInfo(path=str(root.path), source=root.source)


def _config_root(agent: "SuperAgent") -> AuthoringRootInfo:
    """The config root writes ACTUALLY land in.

    ``AuthoringManager`` is built from the agent's own ``config_dir``, which
    only equals ``FACTORY_AGENT_CONFIG_DIR`` for the env/default-built agent;
    an explicitly constructed agent (the library path) reports its own root
    with source ``default`` (i.e. not chosen by the env variable).
    """
    declared = resolve_root("config")
    actual = config_root_for(agent)
    if actual == declared.path:
        return AuthoringRootInfo(path=str(declared.path), source=declared.source)
    return AuthoringRootInfo(path=str(actual), source="default")


def authoring_capabilities(
    policy: AuthoringPolicy, agent: "SuperAgent",
) -> AuthoringCapabilitiesOutput:
    """Project one policy into the FE-facing per-action capability DTO."""
    return AuthoringCapabilitiesOutput(
        config=ConfigSurface(
            read=policy.allows("config", "read"), write=policy.allows("config", "write"),
        ),
        skills=_lifecycle(policy, "skills"),
        steering=_lifecycle(policy, "steering"),
        agent_templates=_lifecycle(policy, "agent_templates"),
        roots=RootsInfo(
            config=_config_root(agent), skills=_root("skills"), steering=_root("steering"),
        ),
    )


def register(mcp: Any, agent: "SuperAgent") -> None:
    policy = policy_for(agent)

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=AuthoringCapabilitiesOutput)
    def agent_authoring_capabilities() -> ToolResult[AuthoringCapabilitiesOutput]:
        """Report the authoring actions this deployment allows, plus its roots."""
        return ok(authoring_capabilities(policy, agent))


__all__ = ["authoring_capabilities", "register"]
