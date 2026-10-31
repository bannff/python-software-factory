"""Standalone persona registry contracts."""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_AGENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")


class AgentConfig(BaseModel):
    """Registered persona; graph nodes may override every behavior field."""

    id: str
    name: str
    model: str = ""
    system_prompt: str
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    exact_tools: bool = False
    description: str = ""
    model_config = ConfigDict(extra="forbid")

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not _AGENT_ID_RE.fullmatch(value):
            raise ValueError(
                f"AgentConfig.id={value!r} is invalid; must match "
                r"^[a-z0-9][a-z0-9_-]{0,127}$"
            )
        return value


__all__ = ["AgentConfig"]
