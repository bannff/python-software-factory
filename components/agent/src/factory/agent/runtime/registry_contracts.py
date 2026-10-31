"""Compatibility facade for registry contracts.

Contracts are split by responsibility to keep every implementation file under
200 LOC. Existing imports intentionally continue to resolve the same classes.
"""
from __future__ import annotations

from typing import Annotated, Union

from pydantic import Field

from .agent_contracts import AgentConfig
from .graph_contracts import (
    AgentNodeRef, CustomNodeRef, EdgeConfig, GraphConfig, GraphNodeRef,
    NodeConfig, NodeRef, SwarmAgentConfig, SwarmConfig, SwarmNodeRef,
)
from .squad_contracts import LocalToolbelt, PhoneHome, SquadConfig, SquadTeam
from .workflow_contracts import (
    SuccessRubric, WorkflowAgentRef, WorkflowConfig, WorkflowSpec,
)

RegistryConfig = Annotated[
    Union[GraphConfig, WorkflowConfig, SwarmConfig],
    Field(discriminator="kind"),
]

# NOTE: SquadConfig is deliberately NOT in RegistryConfig — a squad is a
# deploy spec, not a graph the runtime executes directly.

__all__ = [
    "AgentConfig", "AgentNodeRef", "CustomNodeRef", "EdgeConfig",
    "GraphConfig", "GraphNodeRef", "LocalToolbelt", "NodeConfig", "NodeRef",
    "PhoneHome", "RegistryConfig", "SquadConfig", "SquadTeam", "SuccessRubric",
    "SwarmAgentConfig", "SwarmConfig", "SwarmNodeRef", "WorkflowAgentRef",
    "WorkflowConfig", "WorkflowSpec",
]
