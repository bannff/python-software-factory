"""Public Agent contracts and lazy transport/runtime entry points."""
from __future__ import annotations

from importlib import import_module
from typing import Any

from .runtime.models import ChatStreamEvent, FrontendToolSpec
from .runtime.runtime_contracts import (
    GraphEdge, GraphNode, GraphRequest,
    RuntimeAdapterDescriptor, RuntimeInvocation, RuntimeLifecycleEvent,
    RuntimeResult,
)
from .runtime.runtime_ports import AgentRuntimePort, GraphRuntimePort

_LAZY = {
    "create_server": ("factory.agent.server", "create_mcp_server"),
    "Runtime": ("factory.agent.agent", "SuperAgent"),
    "get_chat_agent": ("factory.agent.runtime.chat", "get_chat_agent"),
    "get_chat_agent_stream": ("factory.agent.runtime.chat", "get_chat_agent_stream"),
    "cancel_chat_turn": ("factory.agent.runtime.chat", "cancel_chat_turn"),
    "close_chat_agent": ("factory.agent.runtime.chat", "close_chat_agent"),
    "resolve_model": (
        "factory.agent.runtime.adapters.langchain_model", "build_langchain_chat_model",
    ),
    "ExecutionManifestV1": (
        "factory.agent.runtime.execution_manifest", "ExecutionManifestV1",
    ),
    "prepare_execution_manifest": (
        "factory.agent.runtime.execution_manifest", "prepare_execution_manifest",
    ),
    "prepare_registered_execution_manifest": (
        "factory.agent.runtime.execution_manifest", "prepare_registered_execution_manifest",
    ),
    "resolve_manifest": ("factory.agent.runtime.execution_manifest", "resolve_manifest"),
    "store_manifest": ("factory.agent.runtime.execution_manifest", "store_manifest"),
    "ManagedLaunchResult": ("factory.agent.runtime.managed_launch", "ManagedLaunchResult"),
    "launch_managed_graph": ("factory.agent.runtime.managed_launch", "launch_managed_graph"),
    "new_run_key": ("factory.agent.runtime.managed_launch", "new_run_key"),
    "CrewConfig": ("factory.agent.runtime.crew_contracts", "CrewConfig"),
    "CrewStore": ("factory.agent.runtime.crew_ports", "CrewStore"),
    "CrewLifecycle": ("factory.agent.runtime.crew_lifecycle", "CrewLifecycle"),
    "ResolvedCrew": ("factory.agent.runtime.crew_lifecycle", "ResolvedCrew"),
    "InMemoryCrewStore": (
        "factory.agent.runtime.adapters.crew_store_memory", "InMemoryCrewStore",
    ),
    "DiskCrewStore": (
        "factory.agent.runtime.adapters.crew_store_disk", "DiskCrewStore",
    ),
    "WorkCompletedEmitterPlugin": (
        "factory.agent.runtime.adapters.strands_work_completed",
        "WorkCompletedEmitterPlugin",
    ),
    "chat_turn_completed_payload": (
        "factory.agent.runtime.adapters.strands_work_completed", "build_payload",
    ),
}


def __getattr__(name: str) -> Any:
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(target[0]), target[1])
    globals()[name] = value
    return value


__all__ = [
    *_LAZY, "ChatStreamEvent", "FrontendToolSpec", "AgentRuntimePort",
    "GraphEdge", "GraphNode", "GraphRequest", "GraphRuntimePort",
    "RuntimeAdapterDescriptor", "RuntimeInvocation", "RuntimeLifecycleEvent",
    "RuntimeResult",
]
