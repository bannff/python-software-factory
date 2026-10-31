"""Trusted registry for framework-specific Agent runtime adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class RuntimeAdapterFactory:
    """Constructors owned by one private framework adapter."""

    adapter_id: str
    agent: Callable[[], Any]
    chat: Callable[[], Any]
    graph: Callable[[], Any]
    coordination: Callable[[], Any]


_FACTORIES: dict[str, RuntimeAdapterFactory] = {}


def register_runtime_adapter(factory: RuntimeAdapterFactory) -> None:
    """Register one trusted startup adapter; duplicate IDs fail closed."""
    if factory.adapter_id in _FACTORIES:
        raise ValueError(f"duplicate runtime adapter: {factory.adapter_id}")
    _FACTORIES[factory.adapter_id] = factory


def get_runtime_adapter(adapter_id: str) -> RuntimeAdapterFactory:
    """Resolve one allowlisted adapter without fallback."""
    try:
        return _FACTORIES[adapter_id]
    except KeyError as exc:
        raise ValueError(f"unknown runtime adapter: {adapter_id}") from exc


def registered_runtime_adapters() -> tuple[str, ...]:
    """Return deterministic trusted adapter IDs for discovery/tests."""
    return tuple(sorted(_FACTORIES))


__all__ = [
    "RuntimeAdapterFactory", "get_runtime_adapter", "register_runtime_adapter",
    "registered_runtime_adapters",
]
