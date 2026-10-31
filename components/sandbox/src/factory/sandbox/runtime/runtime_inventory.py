"""Sandbox runtime inventory and health operations."""
from __future__ import annotations

from typing import Any

from .health import runtime_health
from .models import EnvironmentInfo


def _discover():
    # Indirection preserves the historical monkeypatch surface
    # ``factory.sandbox.runtime.runtime.discover_docker_envs``.
    from . import runtime as runtime_module

    return runtime_module.discover_docker_envs()


class RuntimeInventoryMixin:
    """Environment listing and health for SandboxRuntime."""

    def list_environments(self) -> list[EnvironmentInfo]:
        """List all environments (store + discovered from Docker)."""
        stored = {e.env_id: e for e in self._store.list_environments()}
        # Reconcile: merge discovered Docker envs into the store
        for discovered in _discover():
            if discovered.env_id not in stored:
                self._store.save(discovered)
                stored[discovered.env_id] = discovered
        return list(stored.values())


    def health_check(self) -> dict[str, Any]:
        """Check runtime health."""
        return runtime_health(self._adapter, self._store)
