"""Runtime health aggregation.

Combines adapter + store health with Docker discovery into the single health
dict the runtime exposes. Extracted so the advisory logic (mock adapter while
real Docker targets are visible) lives in one focused place.
"""
from __future__ import annotations

from typing import Any

from .discovery import discover_docker_envs
from .ports import SandboxPort, SandboxStore

_MOCK_WITH_DOCKER_ADVISORY = (
    "Discovery-only mode: Docker targets are visible, but sandbox "
    "provision/exec is still using the mock adapter."
)


def runtime_health(adapter: SandboxPort, store: SandboxStore) -> dict[str, Any]:
    """Return the combined runtime health report."""
    adapter_health = adapter.health_check()
    store_health = store.health_check()
    discovered = discover_docker_envs()
    advisory = None
    if adapter_health.get("adapter") == "mock" and discovered:
        advisory = _MOCK_WITH_DOCKER_ADVISORY
    return {
        "healthy": adapter_health.get("healthy", False),
        "adapter": adapter_health,
        "store": store_health,
        "active_environments": len(store.list_environments()),
        "discovered_environments": len(discovered),
        "advisory": advisory,
    }
