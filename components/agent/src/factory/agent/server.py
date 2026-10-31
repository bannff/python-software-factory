"""Native MCP v2 server interface exposing agent tools, resources, and prompts.

This module is the public MCP surface. It must not contain domain logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import secrets
from typing import TYPE_CHECKING, Any

from .mcp import (
    register_agent_templates, register_authoring, register_authoring_capabilities,
    register_prompts, register_resources, register_tools,
)
from .mcp.views import register as register_views

if TYPE_CHECKING:
    from .agent import SuperAgent


def generate_workflow_id() -> str:
    """Generate a short workflow id (8 hex chars)."""
    return secrets.token_hex(4)


@dataclass
class WorkflowState:
    """Tracks the state of an async workflow execution."""

    status: str = "pending"
    result: Any | None = None
    error: str | None = None
    progress: float = 0.0
    _cancelled: bool = field(default=False, init=False, repr=False)

    def cancel(self) -> None:
        self._cancelled = True
        self.status = "cancelled"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "progress": self.progress,
        }


def _get_default_agent() -> "SuperAgent":
    """Create a default SuperAgent with built-in security presets."""
    from .default_agent import get_default_agent

    return get_default_agent()


def _resolve_approval_names(names: list[str]) -> tuple[str, ...]:
    from factory.mcp_server.interface import resolve_public_mcp_names

    return tuple(resolve_public_mcp_names(names))


def _register_tools(registry: Any, agent: "SuperAgent") -> None:
    register_tools(registry, agent)
    # Authoring registration is unconditional; each tool decides for itself
    # (per-action gate) whether it enters the catalog, so a denied action is
    # absent from tools/list rather than present-but-denied.
    register_authoring(registry, agent)
    register_agent_templates(registry, agent)
    register_authoring_capabilities(registry, agent)
    from .mcp.skills_tools import register as register_skills

    register_skills(registry, agent)
    from .mcp.steering_tools import register as register_steering

    register_steering(registry, agent)
    from .mcp.spawn_tools import register as register_spawn

    register_spawn(registry, agent)
    from .mcp.spawn_background_tools import register as register_background

    register_background(registry, agent)
    from .mcp.list_background_runs_tools import register as register_list_background

    register_list_background(registry, agent)
    from .mcp.cancel_tool import register as register_cancel_turn

    register_cancel_turn(registry, agent)
    from .mcp.async_tools import register as register_async

    register_async(registry, agent, lambda: [])
    register_views(registry)
    from .mcp.managed_graph_tool import register as register_managed_graph

    register_managed_graph(registry, agent)
    from .mcp.session_history import register as register_session_history

    register_session_history(registry)
    from .mcp.session_fork_transcript import register as register_session_fork_transcript

    register_session_fork_transcript(registry)
    from .mcp.session_rewind import register as register_session_rewind

    register_session_rewind(registry)
    from .mcp.session_regenerate import register as register_session_regenerate

    register_session_regenerate(registry)
    from .mcp.crew_tools import register as register_crew

    register_crew(registry, agent)
    from .mcp.model_catalog_tools import register as register_model_catalog

    register_model_catalog(registry, agent)
    from .mcp.approval_policy import register as register_approval_policy
    from .runtime.approval_policy import InMemoryApprovalPolicyStore

    if getattr(agent, "approval_store", None) is None:
        agent.approval_store = InMemoryApprovalPolicyStore()
    register_approval_policy(
        registry,
        agent.approval_store,
        _resolve_approval_names,
    )
    from .mcp.skill_policy import register as register_skill_policy
    from .runtime.skill_store import list_skills
    from .runtime.skill_policy import InMemorySkillPolicyStore

    if getattr(agent, "skill_policy_store", None) is None:
        agent.skill_policy_store = InMemorySkillPolicyStore()
    register_skill_policy(
        registry,
        agent.skill_policy_store,
        lambda: [item.id for item in list_skills()],
    )
    from factory.mcp_utils.interface import set_service

    set_service("agent_skill_policy_store", agent.skill_policy_store)


def create_tool_catalog(agent: "SuperAgent | None" = None) -> Any:
    """Create the transport-neutral Agent tool catalog."""
    from factory.mcp_utils.interface import ToolCatalog

    active_agent = agent or _get_default_agent()
    catalog = ToolCatalog("agent-module")
    _register_tools(catalog, active_agent)
    register_resources(catalog, active_agent)
    register_prompts(catalog)
    return catalog


def create_mcp_server(agent: "SuperAgent | None" = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(agent)


def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for agent brick."""
    return {
        "name": "agent",
        "version": "2.0.0",
        "backends": ["langchain", "langgraph"],
        "features": ["agent_orchestration", "bounded_graphs", "job_management"],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for agent brick."""
    return {"healthy": True, "framework": "langchain-langgraph"}


def describe_config_schema() -> dict[str, Any]:
    """Describe agent configuration schema."""
    return {
        "type": "object",
        "properties": {
            "framework": {"type": "string", "enum": ["langchain", "langgraph"]},
            "model": {"type": "string", "description": "Default LLM model"},
        },
    }
