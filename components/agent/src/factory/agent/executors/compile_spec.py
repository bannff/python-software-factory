"""Pure mapper: WorkflowSpec -> executor config (bd python-factory-tirq Phase 1).

Phase 1 canary: only kind="swarm" is implemented. Other kinds raise
NotImplementedError until their slices land.
"""
from __future__ import annotations

from factory.agent.runtime.registry_contracts import (
    SwarmAgentConfig,
    SwarmConfig,
    GraphConfig,
    WorkflowAgentRef,
    WorkflowConfig,
    WorkflowSpec,
)


def compile_spec(spec: WorkflowSpec) -> SwarmConfig | GraphConfig | WorkflowConfig:
    """Convert a WorkflowSpec into the executor config it targets."""
    match spec.kind:
        case "swarm":
            return _compile_swarm(spec)
        case "graph":
            raise NotImplementedError(
                "compile_spec: graph not yet supported (Phase 1 swarm canary)"
            )
        case "workflow":
            raise NotImplementedError(
                "compile_spec: workflow not yet supported (Phase 1 swarm canary)"
            )


def _compile_swarm(spec: WorkflowSpec) -> SwarmConfig:
    agents = [_compile_agent(a) for a in spec.agents]
    return SwarmConfig(
        id=spec.id,
        name=spec.id,
        entry_point=agents[0].id if agents else "",
        agents=agents,
        context_vars=list(spec.context_vars.keys()),
    )


def _compile_agent(ref: WorkflowAgentRef) -> SwarmAgentConfig:
    return SwarmAgentConfig(
        id=ref.role,
        model=ref.model_id,
        system_prompt=ref.role,
        tools=ref.tools,
        skills=[ref.skill_id],
    )
