"""OpenArcade runtime — minimal DI container for the MCP surface.

The api/blueprint/worker bases all thread a ``runtime`` argument through
``register(mcp, get_runtime)``. OpenArcade's runtime is the env contract:
``config_dir``, ``nci_host``, ``nci_port``. This module is the auditable seam
where those three values get resolved. Tools receive a ``get_runtime`` callable
and call it on every invocation so env changes mid-session are honored.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .env import resolve_config_dir, resolve_nci_target


@dataclass(frozen=True)
class OpenArcadeRuntime:
    config_dir: Path
    nci_host: str
    nci_port: int

    @property
    def nci_target(self) -> str:
        return f"{self.nci_host}:{self.nci_port}"


def get_runtime() -> OpenArcadeRuntime:
    port_env = os.environ.get("OPENARCADE_NCI_PORT")
    host_env = os.environ.get("OPENARCADE_NCI_HOST")
    host, port = resolve_nci_target(
        host_env, int(port_env) if port_env is not None else None
    )
    return OpenArcadeRuntime(
        config_dir=resolve_config_dir(None),
        nci_host=host,
        nci_port=port,
    )
