"""Validate-on-build default agent, swarm, and graph registrations."""
from __future__ import annotations

from typing import Any
from pydantic import TypeAdapter

from ..runtime.registry_contracts import AgentConfig, GraphConfig, RegistryConfig, SwarmConfig
from .defaults_artifacts import ARTIFACT_AGENTS
from .defaults_aws_pentest import AWS_PENTEST_SWARMS
from .defaults_can_agents import CAN_AGENTS
from .defaults_can_pipeline import CAN_PIPELINE_GRAPHS
from .defaults_code_scan import SAST_SCAN_GRAPH
from .defaults_code_scan_hybrid import SAST_HYBRID_GRAPH, SAST_HYBRID_SWARMS
from .defaults_code_scan_single import SAST_SINGLE_GRAPHS, SAST_SINGLE_SWARMS
from .defaults_code_scan_swarm import SAST_SCAN_SWARM
from .defaults_companion_x import COMPANION_X_DEFAULT_AGENT
from .defaults_dast_open import DAST_OPEN_GRAPHS
from .defaults_dev_review import REVIEW_GRAPHS
from .defaults_dataset_research import DATASET_RESEARCH_AGENTS, DATASET_RESEARCH_GRAPHS
from .defaults_developer import DEV_AGENTS
from .defaults_eval_graph import EVAL_GRAPHS, EVAL_SWARMS
from .defaults_pentest import PENTEST_SWARMS
from .defaults_redteam_graph import REDTEAM_AGENTS, REDTEAM_GRAPHS, REDTEAM_SWARMS
from .defaults_redteam_idor_hybrid import DAST_IDOR_HYBRID_GRAPH, DAST_IDOR_HYBRID_SWARMS
from .defaults_redteam_idor_swarm import DAST_IDOR_SWARM
from .defaults_redteam_pentest import RT_PENTEST_SWARMS
from .defaults_sandbox_graph import SANDBOX_GRAPHS
from .defaults_sandbox_graph_only import SANDBOX_GRAPH_ONLY
from .defaults_sandbox_hybrid import SANDBOX_HYBRID_GRAPH, SANDBOX_HYBRID_SWARMS
from .defaults_sast_open import SAST_OPEN_GRAPHS
from .defaults_security_agents import SECURITY_AGENTS
from .defaults_standalone import CODE_REVIEW_SWARM, SECURITY_RECON_SWARM

SECURITY_SWARMS: list[dict] = (
    PENTEST_SWARMS + AWS_PENTEST_SWARMS + REDTEAM_SWARMS
    + RT_PENTEST_SWARMS + EVAL_SWARMS + [SECURITY_RECON_SWARM, CODE_REVIEW_SWARM]
)
EXPERIMENT_SWARMS: list[dict] = (
    [SAST_SCAN_SWARM, DAST_IDOR_SWARM] + SAST_HYBRID_SWARMS
    + DAST_IDOR_HYBRID_SWARMS
    + SANDBOX_HYBRID_SWARMS + SAST_SINGLE_SWARMS
)
EXPERIMENT_GRAPHS: list[dict] = [
    SAST_HYBRID_GRAPH, DAST_IDOR_HYBRID_GRAPH,
    SANDBOX_GRAPH_ONLY, SANDBOX_HYBRID_GRAPH,
] + SAST_SINGLE_GRAPHS

_REGISTRY_ADAPTER: TypeAdapter[RegistryConfig] = TypeAdapter(RegistryConfig)


def _to_graph(value: Any) -> RegistryConfig:
    if isinstance(value, (GraphConfig, SwarmConfig)) or hasattr(value, "model_dump"):
        return value
    if isinstance(value, dict) and value.get("kind") == "workflow":
        return _REGISTRY_ADAPTER.validate_python(value)
    return GraphConfig.model_validate(value)


def _to_swarm(value: Any) -> SwarmConfig:
    return value if isinstance(value, SwarmConfig) else SwarmConfig.model_validate(value)


def _to_agent(value: Any) -> AgentConfig:
    return value if isinstance(value, AgentConfig) else AgentConfig.model_validate(value)


GRAPHS_TYPED: list[RegistryConfig] = [_to_graph(g) for g in (
    REDTEAM_GRAPHS + SANDBOX_GRAPHS
    + EVAL_GRAPHS + [SAST_SCAN_GRAPH] + SAST_OPEN_GRAPHS + DAST_OPEN_GRAPHS
    + EXPERIMENT_GRAPHS + CAN_PIPELINE_GRAPHS + DATASET_RESEARCH_GRAPHS
    + REVIEW_GRAPHS
)]
SWARMS_TYPED: list[SwarmConfig] = [_to_swarm(s) for s in (
    SECURITY_SWARMS + EXPERIMENT_SWARMS
)]
CHAT_AGENTS: list[AgentConfig] = [COMPANION_X_DEFAULT_AGENT]
AGENTS_TYPED: list[AgentConfig] = [
    _to_agent(a) for a in (SECURITY_AGENTS + REDTEAM_AGENTS)
] + CHAT_AGENTS + DEV_AGENTS + ARTIFACT_AGENTS + CAN_AGENTS + DATASET_RESEARCH_AGENTS


def get_default_swarms() -> list[SwarmConfig]:
    return list({item.id: item for item in SWARMS_TYPED}.values())


def get_default_graphs() -> list[RegistryConfig]:
    return list(GRAPHS_TYPED)


def get_default_agents() -> list[AgentConfig]:
    return list(AGENTS_TYPED)


__all__ = [
    "AGENTS_TYPED", "ARTIFACT_AGENTS", "CHAT_AGENTS", "COMPANION_X_DEFAULT_AGENT", "DEV_AGENTS",
    "EXPERIMENT_GRAPHS", "EXPERIMENT_SWARMS", "GRAPHS_TYPED", "REDTEAM_AGENTS",
    "REDTEAM_GRAPHS", "SECURITY_AGENTS", "SECURITY_SWARMS", "SWARMS_TYPED",
    "get_default_agents", "get_default_graphs", "get_default_swarms",
]
