"""Squad registry contract — a deployable team-of-agents, defined as DATA.

A *squad* is a team of agents packaged to be deployed into a sandbox
container: a team topology + a local toolbelt + a target sandbox profile +
phone-home config. It is pure data — there is NO per-squad Python file. One
constant squad runner executes any ``SquadConfig``.

Two doors, one schema:
- **Durable** squad = a ``kind="squad"`` YAML registered on disk.
- **Ephemeral** squad = the same schema injected at runtime by an agent
  (e.g. the chat agent via an authoring tool), no persistence required.

Tool split (see issue python-factory #763): a squad binds BOTH
- ``toolbelt`` — LOCAL tools that execute INSIDE the container on the target
  repo's filesystem (shell/exec, file read/write/edit, grep), and
- ``phone_home`` — REMOTE Companion-X tools (memory/KB/graph) reached over
  MCP. Local job tools ship with the squad; the shared brain stays in HQ.

This contract is intentionally NOT part of the executable ``RegistryConfig``
union: a squad is a deploy spec, not a graph the LangGraph runtime executes
directly. The runner reads the squad, then runs its embedded ``team``.
"""
from __future__ import annotations

import re
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .graph_contracts import GraphConfig, SwarmConfig

_SQUAD_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")

# The squad's team topology reuses the already-validated graph/swarm models,
# dispatched on their own ``kind`` discriminator. A ``GraphConfig`` whose
# nodes are ``SwarmNodeRef`` expresses the graph-of-swarms shape.
SquadTeam = Annotated[Union[GraphConfig, SwarmConfig], Field(discriminator="kind")]


class LocalToolbelt(BaseModel):
    """Local tools bound to the squad, executing inside its container against
    the target repo's filesystem — distinct from remote phone-home tools.

    ``tools`` are runner-resolved local tool ids (e.g. ``shell``,
    ``file_read``, ``file_write``, ``edit``, ``grep``). The names are a
    contract with the squad runner, not MCP tool names.
    """

    tools: list[str] = Field(default_factory=list)
    model_config = ConfigDict(extra="forbid")


class PhoneHome(BaseModel):
    """How the squad reaches its bearer-free per-launch MCP proxy.

    ``mcp_url`` is proxy-only and must never point at the upstream Companion-X
    gateway. Deployed squads require an explicit non-empty ``tool_allowlist``;
    ``None`` is retained only for schema-compatible local-only configurations
    and fails loud during proxy preparation.
    """

    mcp_url: str | None = None
    tool_allowlist: list[str] | None = None
    @field_validator("tool_allowlist")
    @classmethod
    def _validate_allowlist(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if not value or len(value) != len(set(value)):
            raise ValueError("PhoneHome.tool_allowlist must be non-empty and unique")
        if any(not isinstance(name, str) or not name.strip() for name in value):
            raise ValueError("PhoneHome.tool_allowlist requires exact non-empty tool names")
        return value

    model_config = ConfigDict(extra="forbid")


class SquadConfig(BaseModel):
    """A deployable team-of-agents, defined entirely as data."""

    id: str
    kind: Literal["squad"] = "squad"
    name: str
    description: str = ""
    # Informational: rust, python, typescript, ... The squad runtime is always
    # Python/LangGraph regardless; this documents the TARGET the squad edits.
    target_language: str = ""
    # References a sandbox profile name (e.g. "rust-sdk") — the target toolchain
    # + base image. The squad-runtime venv is a separate isolated overlay.
    sandbox_profile: str
    # Inline team topology (graph or swarm) — reuses validated models.
    team: SquadTeam
    toolbelt: LocalToolbelt = Field(default_factory=LocalToolbelt)
    # Default LLM for the squad; per-node model overrides still apply.
    model: str | None = None
    # Extra Python packages installed into the squad's isolated venv at boot.
    extra_deps: list[str] = Field(default_factory=list)
    phone_home: PhoneHome = Field(default_factory=PhoneHome)
    model_config = ConfigDict(extra="forbid")

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not _SQUAD_ID_RE.fullmatch(value):
            raise ValueError(
                f"SquadConfig.id={value!r} is invalid; must match "
                r"^[a-z0-9][a-z0-9_-]{0,127}$"
            )
        return value

    @field_validator("sandbox_profile")
    @classmethod
    def _validate_profile(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("SquadConfig.sandbox_profile must be non-empty")
        return value


__all__ = ["SquadConfig", "LocalToolbelt", "PhoneHome", "SquadTeam"]
