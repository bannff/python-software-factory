"""Closed, framework-neutral implementation registry for replay evidence."""
from __future__ import annotations

from typing import Any

from .canonical import canonical_bytes, sha256
from .descriptors import (
    ConditionDescriptor, HookDescriptor, LocalToolDescriptor, PluginDescriptor,
)

_ASSEMBLER_VERSION = "2"


def _langchain_version() -> str:
    """Dormant-runtime laziness: langchain lives in langgraph-legacy."""
    from importlib.metadata import version as _v
    return _v("langchain")


_BUILTINS = frozenset({
    "editor", "file_read", "file_write", "http_request", "python_repl",
    "retrieve", "shell", "think", "use_llm",
})
_PLUGIN_SPECS = {
    kind: (f"factory.agent.policy.{kind}", _ASSEMBLER_VERSION)
    for kind in (
        "agent-skills", "tool-runaway-guard", "sast", "sast-steering",
        "context-offloader", "swarm-collaboration",
    )
}
_HOOK_SPECS = {
    kind: (f"factory.agent.event.{kind}", _ASSEMBLER_VERSION)
    for kind in ("graph-lifecycle", "swarm-lifecycle", "no-revisit")
}
_CONDITION_SPECS = {
    "all-predecessors-valid": (
        "factory.agent.condition.all_predecessors_valid", _ASSEMBLER_VERSION,
    ),
}


def _digest(kind: str, implementation_id: str, implementation_version: str,
            config: dict[str, Any]):
    return sha256(canonical_bytes({
        "kind": kind, "implementation_id": implementation_id,
        "implementation_version": implementation_version, "config": config,
    }))


def is_local_tool(name: str) -> bool:
    return name in _BUILTINS


def freeze_local_tool(name: str) -> LocalToolDescriptor:
    if name not in _BUILTINS:
        raise ValueError(f"unknown local tool: {name!r}")
    implementation_id = f"langchain-tool:{name}"
    implementation_version = _langchain_version()
    config = {"spec": name}
    return LocalToolDescriptor(
        name=name, implementation_id=implementation_id,
        implementation_version=implementation_version, config=config,
        digest=_digest(name, implementation_id, implementation_version, config),
    )


def verify_local_tool(descriptor: LocalToolDescriptor) -> str:
    expected = freeze_local_tool(descriptor.name)
    if descriptor != expected:
        raise ValueError(f"local tool implementation binding changed: {descriptor.name!r}")
    return str(descriptor.config["spec"])


def _freeze(kind: str, config: dict[str, Any], specs: dict[str, tuple[str, str]], cls: Any):
    try:
        implementation_id, implementation_version = specs[kind]
    except KeyError as exc:
        raise ValueError(f"unknown manifest behavior: {kind!r}") from exc
    return cls(
        kind=kind, implementation_id=implementation_id,
        implementation_version=implementation_version, config=config,
        digest=_digest(kind, implementation_id, implementation_version, config),
    )


def freeze_plugin(kind: str, config: dict[str, Any]) -> PluginDescriptor:
    return _freeze(kind, config, _PLUGIN_SPECS, PluginDescriptor)


def verify_plugin(descriptor: PluginDescriptor) -> None:
    if descriptor != freeze_plugin(descriptor.kind, dict(descriptor.config)):
        raise ValueError(f"plugin implementation binding changed: {descriptor.kind!r}")


def freeze_hook(kind: str, config: dict[str, Any]) -> HookDescriptor:
    return _freeze(kind, config, _HOOK_SPECS, HookDescriptor)


def verify_hook(descriptor: HookDescriptor) -> None:
    if descriptor != freeze_hook(descriptor.kind, dict(descriptor.config)):
        raise ValueError(f"hook implementation binding changed: {descriptor.kind!r}")


def freeze_condition(kind: str, predecessors: tuple[str, ...]) -> ConditionDescriptor:
    return _freeze(
        kind, {"predecessors": list(predecessors)},
        _CONDITION_SPECS, ConditionDescriptor,
    )


def verify_condition(descriptor: ConditionDescriptor) -> tuple[str, ...]:
    predecessors = tuple(str(item) for item in descriptor.config["predecessors"])
    if descriptor != freeze_condition(descriptor.kind, predecessors):
        raise ValueError(f"condition implementation binding changed: {descriptor.kind!r}")
    return predecessors


__all__ = [
    "freeze_condition", "freeze_hook", "freeze_local_tool", "freeze_plugin",
    "is_local_tool", "verify_condition", "verify_hook", "verify_local_tool",
    "verify_plugin",
]
