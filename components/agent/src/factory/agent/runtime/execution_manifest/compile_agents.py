"""Preparation-time Agent and native Swarm materialization."""
from __future__ import annotations

import os
from typing import Any

from .base import json_object
from .nodes import AgentManifest, SwarmLimits, SwarmManifest
from .plugin_freeze import graph_plugins, swarm_hooks, swarm_member_plugins
from .preparation_support import (
    conversation, freeze_model, freeze_schema, freeze_skills, freeze_tools,
    partition_tools, render_text,
)


def _mcp_scope(node: Any, inherited: list[str] | None) -> tuple[str, list[str]]:
    if "mcp_tool_allowlist" not in node.model_fields_set or node.mcp_tool_allowlist is None:
        return "inherit", list(inherited or [])
    if not node.mcp_tool_allowlist:
        return "empty", []
    return "explicit", list(node.mcp_tool_allowlist)


def _node_behavior(node: Any) -> Any:
    """Resolve node-over-persona behavior without a runtime executor shim."""
    from factory.agent.runtime.agent_contracts import AgentConfig
    from factory.agent.runtime.personas import resolve_agent_config

    base = resolve_agent_config(node.agent_id) if node.agent_id else None
    explicit = node.model_fields_set

    def value(name: str, fallback: Any) -> Any:
        candidate = getattr(node, name)
        return candidate if name in explicit and candidate is not None else fallback

    model = value("model", base.model if base else None)
    prompt = value("system_prompt", base.system_prompt if base else None)
    if not model:
        # Empty = inherit the process default (COMPANION_X_CHAT_MODEL), the
        # same convention LangChainModelCache.effective_id applies at
        # runtime; manifests still freeze a concrete id, so substitute the
        # default here rather than rejecting deployment-inherited personas.
        model = os.environ.get("COMPANION_X_CHAT_MODEL", "").strip() or (
            "us.anthropic.claude-sonnet-4-6"
        )
    if not model or prompt is None:
        raise ValueError(f"agent node {node.id!r} requires concrete model and prompt")
    inherited_context = dict(base.context) if base else {}
    inherited_context.update(node.context or {})
    return AgentConfig(
        id=node.id, name=node.id, model=model, system_prompt=prompt,
        description=value("description", base.description if base else ""),
        tools=value("tools", list(base.tools) if base else []),
        skills=value("skills", list(base.skills) if base else []),
        context=inherited_context,
        exact_tools=True if node.read_only else (base.exact_tools if base else False),
    )


def _persona_scope(
    node: Any, config: Any, graph_allowlist: list[str] | None,
) -> tuple[list[str], str, list[str]]:
    """Split persona tools; exact personas freeze their MCP names as scope.

    Mirrors ``capability_policy.effective_persona_scope`` at preparation time
    so a registered persona whose ``tools`` name MCP tools (e.g. Developer's
    ``devtools_*``) compiles instead of failing as unknown local built-ins.
    """
    local, persona_mcp = partition_tools(config.tools)
    mode, resolved = _mcp_scope(node, graph_allowlist)
    if mode == "inherit" and config.exact_tools and persona_mcp:
        mode = "explicit"
        resolved = (persona_mcp if graph_allowlist is None
                    else [name for name in persona_mcp if name in graph_allowlist])
    return local, mode, resolved


def owner_enabled_skills(skills: list[str]) -> list[str]:
    """Subtract the ambient owner's disabled skills (empty policy = all attach).

    The frozen bundle then reflects what actually ran, so replay evidence and
    the owner's Settings agree. Resolution goes through the ``skill_policy``
    service registered by the Agent server; absent service or owner → no-op.
    """
    from factory.mcp_utils.interface import get_envelope, get_service
    store = get_service("agent_skill_policy_store")
    envelope = get_envelope() or {}
    tenant, owner = envelope.get("tenant_id"), envelope.get("principal_id")
    if store is None or not isinstance(tenant, str) or not isinstance(owner, str):
        return list(skills)
    try:
        return store.get(tenant, owner).apply(list(skills))
    except (OSError, ValueError):
        return list(skills)


def compile_agent(node: Any, context: dict[str, Any],
                  graph_allowlist: list[str] | None) -> AgentManifest:
    config = _node_behavior(node)
    merged = {**context, **config.context}
    local, mode, resolved = _persona_scope(node, config, graph_allowlist)
    skills = freeze_skills(owner_enabled_skills(config.skills))
    return AgentManifest(
        id=node.id, name=node.id, description=config.description,
        system_prompt=render_text(config.system_prompt, merged),
        model=freeze_model(config.model),
        tools=freeze_tools(local, mode, resolved, config.exact_tools),
        skills=skills, output_schema=freeze_schema(node.output_schema),
        plugins=graph_plugins(node.id, skills, context),
        conversation=conversation(), initial_state=json_object(config.context),
        trace_attributes=json_object({"agent_id": node.id}),
    )


def compile_swarm(node_id: str, swarm: Any,
                  context: dict[str, Any]) -> SwarmManifest:
    ids = [item.id for item in swarm.agents]
    members: list[AgentManifest] = []
    for item in swarm.agents:
        member_context = {**context, "agent_id": item.id}
        skills = freeze_skills(item.skills)
        tools = freeze_tools(item.tools, "inherit", [], False)
        if any("handoff_to_agent" in tool.name for tool in tools.local):
            raise ValueError("predeclared handoff_to_agent conflicts with native swarm handoff")
        members.append(AgentManifest(
            id=item.id, name=item.name or item.id, description=item.description,
            system_prompt=render_text(item.system_prompt, member_context),
            # Empty = inherit the process default, same as _node_behavior —
            # deployment-inherited personas (model="") must freeze concrete ids.
            model=freeze_model(item.model or os.environ.get(
                "COMPANION_X_CHAT_MODEL", "").strip() or "us.anthropic.claude-sonnet-4-6"),
            tools=tools, skills=skills,
            output_schema=None,
            plugins=swarm_member_plugins(item.id, ids, skills),
            conversation=conversation(), initial_state={},
            trace_attributes={"agent_id": item.id},
        ))
    return SwarmManifest(
        id=node_id, name=swarm.name, description=swarm.description,
        members=tuple(members), entry_point=swarm.entry_point,
        limits=SwarmLimits(
            max_handoffs=swarm.max_handoffs, max_iterations=swarm.max_iterations,
            execution_timeout=swarm.execution_timeout, node_timeout=swarm.node_timeout,
            repetitive_handoff_detection_window=swarm.repetitive_handoff_detection_window,
            repetitive_handoff_min_unique_agents=swarm.repetitive_handoff_min_unique_agents,
        ), plugins=(), hooks=swarm_hooks(node_id, context),
    )


__all__ = ["compile_agent", "compile_swarm", "owner_enabled_skills"]
