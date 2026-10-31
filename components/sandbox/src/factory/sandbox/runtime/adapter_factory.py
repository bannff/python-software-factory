"""Adapter and store factories driven by environment variables.

Extracted from ``runtime.py`` so the concrete adapter/store selection stays a
small, SRP-clean seam. Both factories lazy-import their concrete classes so
optional backends (docker, localstack, graph) never load unless selected.
"""
from __future__ import annotations

import os

from .ports import SandboxPort, SandboxStore


def create_adapter() -> SandboxPort:
    """Create adapter based on SANDBOX_ADAPTER env var."""
    adapter_name = os.environ.get("SANDBOX_ADAPTER", "mock")
    match adapter_name:
        case "docker":
            from .adapters.docker_adapter import DockerAdapter
            return DockerAdapter()
        case "localstack":
            from .adapters.localstack_adapter import LocalStackAdapter
            return LocalStackAdapter(
                compose_dir=os.environ.get("LOCALSTACK_COMPOSE_DIR"),
            )
        case "mock" | _:
            from .adapters.mock import MockAdapter
            return MockAdapter()


def create_store() -> SandboxStore:
    """Create store based on SANDBOX_PERSISTENCE env var."""
    backend = os.environ.get("SANDBOX_PERSISTENCE", "memory")
    match backend:
        case "graph":
            from .adapters.graph_store import GraphSandboxStore
            return GraphSandboxStore()
        case "memory" | _:
            from .adapters.memory_store import MemorySandboxStore
            return MemorySandboxStore()
