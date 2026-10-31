"""Default SuperAgent construction with built-in security presets.

Split out of ``server.py`` to keep that file under the 200 LOC ceiling --
this is a large, self-contained bootstrap concern (durable config root,
registries, approval/skill policy stores) distinct from tool
registration.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .agent import SuperAgent


def get_default_agent() -> "SuperAgent":
    """Create a default SuperAgent with built-in security presets."""
    from .agent import SuperAgent
    from .authoring.roots import ensure_root
    from .registry.agents import AgentRegistry
    from .registry.swarms import SwarmRegistry
    from .registry.graphs import GraphRegistry
    from .registry.tools import ToolRegistry
    from .registry.defaults import get_default_swarms, get_default_agents, get_default_graphs

    # Durable owner-scoped root (never a throw-away temp dir): personas and
    # settings authored at runtime must survive a restart.
    config_root = ensure_root("config").path
    agent = SuperAgent(config_dir=str(config_root))
    # The user-persona store MUST read the same directory the
    # AuthoringManager writes to (``<config_dir>/agents``) so a persona
    # authored via ``agent_create_agent`` + reload is picked up by the
    # unified merge (bd:python-factory-d4roe.2). AuthoringManager uses
    # ``AuthoringPaths(root=config_dir).agents_dir``; mirror it here.
    agents_dir = config_root / "agents"
    agent.agent_registry = AgentRegistry(agents_dir)
    agent.swarm_registry = SwarmRegistry(config_root)
    agent.graph_registry = GraphRegistry(config_root)
    agent.tool_registry = ToolRegistry(config_root)
    agent.workflows = {}
    agent.settings = {}
    from .runtime.adapters.approval_policy_store import SqliteApprovalPolicyStore
    agent.approval_store = SqliteApprovalPolicyStore(os.getenv(
        "COMPANION_X_APPROVAL_POLICY_DB_PATH", "./.storage/agent-approval.db",
    ))
    from .runtime.adapters.skill_policy_store import SqliteSkillPolicyStore
    agent.skill_policy_store = SqliteSkillPolicyStore(os.getenv(
        "COMPANION_X_APPROVAL_POLICY_DB_PATH", "./.storage/agent-approval.db",
    ))
    agent._initialized = True

    # Register built-in security presets
    for swarm in get_default_swarms():
        agent.swarm_registry.swarms[swarm.id] = swarm
    for ag in get_default_agents():
        agent.agent_registry.agents[ag.id] = ag
    for graph in get_default_graphs():
        agent.graph_registry.graphs[graph.id] = graph

    # Unify the persona read path (bd:python-factory-d4roe.1): wire the
    # registry's user-persona store process-wide so the chat resolver
    # and the discovery surface agree. The pre-seed loop above already
    # populated built-ins; the disk store over the fresh temp dir is
    # empty, so unified_personas() == built-ins (byte-identical). User
    # personas authored later (authoring write_config + reload) flow
    # through this same store to both the registry and the resolver.
    from factory.agent.registry.unified import set_default_store
    set_default_store(agent.agent_registry.store)

    return agent


__all__ = ["get_default_agent"]
