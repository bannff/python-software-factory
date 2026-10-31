"""Freeze registry-declared plugins and HookProviders."""
from __future__ import annotations

import os
from typing import Any

from .behavior_registry import freeze_hook, freeze_plugin
from .descriptors import HookDescriptor, PluginDescriptor, SkillBundle

# Explicit registration data: no domain, prompt, or identifier substring inference.
_AGENT_PLUGIN_PROFILES = {
    "gptoss-sast": ("sast", "sast-steering"),
    "sonnet-sast": ("sast", "sast-steering"),
    "glm5-sast": ("sast", "sast-steering"),
}


def _offload() -> PluginDescriptor:
    backend = os.getenv("STRANDS_OFFLOAD_BACKEND", "file").lower()
    config: dict[str, Any] = {
        "backend": backend,
        "max_result_tokens": int(os.getenv("STRANDS_OFFLOAD_MAX_TOKENS", "8000")),
        "preview_tokens": int(os.getenv("STRANDS_OFFLOAD_PREVIEW_TOKENS", "2500")),
        "include_retrieval_tool": True,
    }
    if backend == "file":
        config["path"] = os.getenv("STRANDS_OFFLOAD_DIR", "./.storage/offloaded")
    elif backend == "s3":
        bucket = os.getenv("STRANDS_OFFLOAD_BUCKET")
        if not bucket:
            raise ValueError("STRANDS_OFFLOAD_BUCKET required for replayable s3 offload")
        config.update(bucket=bucket, prefix=os.getenv("STRANDS_OFFLOAD_PREFIX", ""))
    elif backend != "memory":
        raise ValueError(f"unknown ContextOffloader backend: {backend!r}")
    return freeze_plugin("context-offloader", config)


def graph_plugins(agent_id: str, skills: SkillBundle,
                  invocation_context: dict[str, Any]) -> tuple[PluginDescriptor, ...]:
    plugins: list[PluginDescriptor] = []
    if skills.names:
        plugins.append(freeze_plugin(
            "agent-skills", {"skill_bundle_digest": skills.digest.value},
        ))
    plugins.append(freeze_plugin(
        "tool-runaway-guard",
        {"agent_id": agent_id, "tool_limits": {}, "total_limit": 100},
    ))
    for kind in _AGENT_PLUGIN_PROFILES.get(agent_id, ()):
        config = ({"workspace": str(invocation_context.get(
            "sast_workspace", "/tmp/factory-sast",
        ))} if kind == "sast" else {})
        plugins.append(freeze_plugin(kind, config))
    plugins.append(_offload())
    return tuple(plugins)


def swarm_member_plugins(agent_id: str, teammates: list[str],
                         skills: SkillBundle) -> tuple[PluginDescriptor, ...]:
    plugins: list[PluginDescriptor] = []
    if skills.names:
        plugins.append(freeze_plugin(
            "agent-skills", {"skill_bundle_digest": skills.digest.value},
        ))
    plugins.extend((
        freeze_plugin("swarm-collaboration", {
            "agent_id": agent_id, "teammates": teammates,
        }),
        _offload(),
    ))
    return tuple(plugins)


def graph_hooks(graph_id: str, context: dict[str, Any]) -> tuple[HookDescriptor, ...]:
    return (freeze_hook("graph-lifecycle", {
        "graph_id": graph_id, "run_id": str(context.get("run_id", "")),
    }),)


def swarm_hooks(swarm_id: str, context: dict[str, Any]) -> tuple[HookDescriptor, ...]:
    return (
        freeze_hook("swarm-lifecycle", {
            "swarm_id": swarm_id, "run_id": str(context.get("run_id", "")),
        }),
        freeze_hook("no-revisit", {}),
    )


__all__ = ["graph_hooks", "graph_plugins", "swarm_hooks", "swarm_member_plugins"]
