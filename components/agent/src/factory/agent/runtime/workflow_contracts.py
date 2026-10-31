"""Workflow registry contracts."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .graph_contracts import EdgeConfig


class WorkflowConfig(BaseModel):
    id: str
    kind: Literal["workflow"]
    factory: str
    name: str
    description: str = ""
    required_bricks: list[str] = Field(default_factory=list)
    context_vars: list[str] = Field(default_factory=list)
    tool_allowlist: list[str] | None = None
    execution_timeout: float = 5400.0
    node_timeout: float = 1800.0
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _factory_must_resolve(self) -> "WorkflowConfig":
        from factory.agent.registry.factories import known_factories
        known = known_factories()
        if self.factory not in known:
            raise ValueError(
                f"WorkflowConfig.factory={self.factory!r} is not registered. "
                f"Known: {known}"
            )
        return self


class SuccessRubric(BaseModel):
    output_entity_type: str
    match_on: tuple[str, ...]
    ground_truth_ref: str
    reward_formula: str = "f1"
    model_config = ConfigDict(extra="forbid")


class WorkflowAgentRef(BaseModel):
    role: str
    skill_id: str
    model_id: str
    tools: list[str] = Field(default_factory=list)
    model_config = ConfigDict(extra="forbid")


class WorkflowSpec(BaseModel):
    id: str
    kind: Literal["swarm", "graph", "workflow"]
    agents: list[WorkflowAgentRef] = Field(default_factory=list)
    edges: list[EdgeConfig] = Field(default_factory=list)
    success_rubric: SuccessRubric
    gt_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    context_vars: dict[str, Any] = Field(default_factory=dict)
    model_config = ConfigDict(extra="forbid")


__all__ = [
    "SuccessRubric", "WorkflowAgentRef", "WorkflowConfig", "WorkflowSpec",
]
