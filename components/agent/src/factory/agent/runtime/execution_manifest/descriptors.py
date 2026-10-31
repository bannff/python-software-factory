"""Replay-complete, version-bound behavior descriptors."""
from __future__ import annotations

from typing import Literal

from pydantic import JsonValue, model_validator

from .base import DigestValue, FrozenModel


class ModelDescriptor(FrozenModel):
    provider: Literal["literal", "bedrock", "ollama", "mantle"]
    model_id: str
    settings: dict[str, JsonValue]


class LocalToolDescriptor(FrozenModel):
    name: str
    implementation_id: str
    implementation_version: str
    config: dict[str, JsonValue]
    digest: DigestValue


class ToolDescriptor(FrozenModel):
    local: tuple[LocalToolDescriptor, ...]
    mcp_mode: Literal["inherit", "empty", "explicit"]
    resolved_mcp_allowlist: tuple[str, ...]
    exact_tools: bool


class SkillFile(FrozenModel):
    path: str
    content: str
    digest: DigestValue


class SkillBundle(FrozenModel):
    names: tuple[str, ...]
    files: tuple[SkillFile, ...]
    digest: DigestValue

    @model_validator(mode="after")
    def _complete(self) -> "SkillBundle":
        if bool(self.names) != bool(self.files):
            raise ValueError("skill names and files must both be empty or non-empty")
        return self


class OutputSchemaDescriptor(FrozenModel):
    name: str
    json_schema: dict[str, JsonValue]
    digest: DigestValue


class PluginDescriptor(FrozenModel):
    kind: Literal[
        "agent-skills", "tool-runaway-guard", "sast", "sast-steering",
        "context-offloader", "swarm-collaboration",
    ]
    implementation_id: str
    implementation_version: str
    config: dict[str, JsonValue]
    digest: DigestValue


class HookDescriptor(FrozenModel):
    kind: Literal["graph-lifecycle", "swarm-lifecycle", "no-revisit"]
    implementation_id: str
    implementation_version: str
    config: dict[str, JsonValue]
    digest: DigestValue


class ConditionDescriptor(FrozenModel):
    kind: Literal["all-predecessors-valid"]
    implementation_id: str
    implementation_version: str
    config: dict[str, JsonValue]
    digest: DigestValue


class ConversationDescriptor(FrozenModel):
    kind: Literal["sliding-window"] = "sliding-window"
    window_size: int
    should_truncate_results: bool
    per_turn: int


__all__ = [
    "ConditionDescriptor", "ConversationDescriptor", "HookDescriptor",
    "LocalToolDescriptor", "ModelDescriptor", "OutputSchemaDescriptor",
    "PluginDescriptor", "SkillBundle", "SkillFile", "ToolDescriptor",
]
