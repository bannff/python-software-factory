"""Bind-mount a per-launch workload UDS into a sandbox container.

The trusted host (Workflow) creates a per-launch Unix socket for the scoped,
bearer-free MCP proxy; Sandbox bind-mounts it into the container at the
canonical path and forces ``MCP_PROXY_SOCKET`` to match so the two can never
drift. No token/credential is ever mounted — the container dials the socket and
Permissions authorizes upstream. Container removal unmounts the bind; the
orphan sweep reaps crashed/exited labeled containers.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import stat
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

CANONICAL_PROXY_SOCKET = "/run/companion-x/mcp.sock"

_RunFn = Callable[..., tuple[int, str, str]]


def validate_socket(host_path: str) -> None:
    """Fail loud unless ``host_path`` exists and is a Unix socket."""
    try:
        mode = Path(host_path).stat().st_mode
    except OSError as exc:
        raise ValueError(f"workload proxy socket not found: {host_path}") from exc
    if not stat.S_ISSOCK(mode):
        raise ValueError(f"workload proxy path is not a socket: {host_path}")


def build_mount_args(config: dict[str, Any]) -> list[str]:
    """Build ``docker run -v`` args for generic mounts + the workload UDS."""
    args: list[str] = []
    for mount in config.get("mounts", []) or []:
        suffix = ":ro" if mount.get("read_only") else ""
        args.extend(["-v", f"{mount['source']}:{mount['target']}{suffix}"])
    socket = config.get("proxy_socket")
    if socket:
        validate_socket(socket)
        args.extend(["-v", f"{socket}:{CANONICAL_PROXY_SOCKET}"])
    return args


def proxy_env(config: dict[str, Any]) -> dict[str, str]:
    """Env forced by the mount so ``MCP_PROXY_SOCKET`` always matches target."""
    if not config.get("proxy_socket"):
        return {}
    return {"MCP_PROXY_SOCKET": CANONICAL_PROXY_SOCKET}


_WORKLOAD_LABEL = "factory.workload"
_SWEEP_FORMAT = "{{.ID}}\t{{.Status}}\t{{.Labels}}"
_SECRET_EVIDENCE_HOLD_SECONDS = 600
_EMPTY_NETWORK_GRACE_SECONDS = 120
_FULL_CONTAINER_ID = re.compile(r"^[0-9a-f]{64}$")
_OWNED_NETWORK = re.compile(r"^factory-sandbox-[a-z0-9-]+$")
_RECHECK_FORMAT = (
    "{{.Id}}\t{{.State.Status}}\t{{.State.FinishedAt}}\t"
    "{{.State.StartedAt}}\t{{json .Config.Labels}}"
)


def sweep_orphans(
    run: Callable[..., tuple[int, str, str]],
    label: str = "factory.sandbox=true",
    *, now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Reap exited/dead labeled containers (delegates to orphan_sweeper)."""
    from .orphan_sweeper import sweep_orphans as _sweep

    return _sweep(run, label, now=now)
