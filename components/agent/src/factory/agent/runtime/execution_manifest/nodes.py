"""Materialized Agent and native Swarm node contracts."""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field, JsonValue, model_validator

from .base import FrozenModel
from .descriptors import (
    ConversationDescriptor, HookDescriptor, ModelDescriptor,
    OutputSchemaDescriptor, PluginDescriptor, SkillBundle, ToolDescriptor,
)


class AgentManifest(FrozenModel):
    id: str
    type: Literal["agent"] = "agent"
    name: str
    description: str
    system_prompt: str
    model: ModelDescriptor
    tools: ToolDescriptor
    skills: SkillBundle
    output_schema: OutputSchemaDescriptor | None
    plugins: tuple[PluginDescriptor, ...]
    conversation: ConversationDescriptor
    initial_state: dict[str, JsonValue]
    trace_attributes: dict[str, JsonValue]


class SwarmLimits(FrozenModel):
    max_handoffs: int
    max_iterations: int
    execution_timeout: float
    node_timeout: float
    repetitive_handoff_detection_window: int
    repetitive_handoff_min_unique_agents: int


class SwarmManifest(FrozenModel):
    id: str
    type: Literal["swarm"] = "swarm"
    name: str
    description: str
    members: tuple[AgentManifest, ...]
    entry_point: str
    limits: SwarmLimits
    plugins: tuple[PluginDescriptor, ...]
    hooks: tuple[HookDescriptor, ...]

    @model_validator(mode="after")
    def _topology(self) -> "SwarmManifest":
        ids = [member.id for member in self.members]
        if len(ids) != len(set(ids)) or self.entry_point not in ids:
            raise ValueError("swarm members must be unique and include entry point")
        for member in self.members:
            if any("handoff_to_agent" in tool.name for tool in member.tools.local):
                raise ValueError("Swarm handoff tool is SDK-owned")
        return self


ManifestNode = Annotated[
    Union[AgentManifest, SwarmManifest], Field(discriminator="type")
]


__all__ = ["AgentManifest", "ManifestNode", "SwarmLimits", "SwarmManifest"]
