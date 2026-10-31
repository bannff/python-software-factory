"""Discover Docker cleanup candidates from the Docker CLI listing."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Callable

from .orphan_recheck import _reason_from_status

_RunFn = Callable[..., tuple[int, str, str]]

_WORKLOAD_LABEL = "factory.workload"
_SWEEP_FORMAT = "{{.ID}}\t{{.Status}}\t{{.Labels}}"
_FULL_CONTAINER_ID = re.compile(r"^[0-9a-f]{64}$")


def collect_reapable(
    run: _RunFn, label: str, *, now: datetime | None = None,
) -> list[dict[str, Any]]:
    """List exited/dead labeled containers with their workload policy id.

    CRITICAL: called BEFORE ``docker rm -f`` — removal erases labels, so the
    reaper must capture ``factory.workload`` (and the reap reason) first.
    Reuses ``discovery._parse_labels`` for label parsing (no duplication).
    """
    from ..discovery import _parse_labels

    code, stdout, _ = run([
        "docker", "ps", "-a", "--no-trunc", "--filter", f"label={label}",
        "--filter", "status=exited", "--filter", "status=dead",
        "--format", _SWEEP_FORMAT,
    ])
    if code != 0:
        return []
    reaped: list[dict[str, Any]] = []
    for line in stdout.strip().splitlines():
        parts = line.split("\t")
        name = parts[0] if parts else ""
        if not _FULL_CONTAINER_ID.fullmatch(name):
            continue
        status = parts[1] if len(parts) > 1 else ""
        labels = _parse_labels(parts[2] if len(parts) > 2 else "")
        candidate = {
            "container_id": name,
            "policy_id": labels.get(_WORKLOAD_LABEL),
            "reason": _reason_from_status(status),
        }
        if network_name := labels.get("factory.sandbox.peer_network_name"):
            candidate["network_name"] = network_name
        reaped.append(candidate)
    return reaped


def _collect_timed_out_secret(
    run: _RunFn, label: str, *, now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Select only running secret containers with a verified elapsed timeout."""
    from ..discovery import _parse_labels

    code, stdout, _ = run([
        "docker", "ps", "-a", "--no-trunc", "--filter", f"label={label}",
        "--filter", "label=factory.sandbox.secret_output_suppressed=true",
        "--filter", "status=running", "--format", _SWEEP_FORMAT,
    ])
    if code != 0:
        return []
    candidates: list[dict[str, Any]] = []
    for line in stdout.strip().splitlines():
        parts = line.split("\t")
        container_id = parts[0] if parts else ""
        if not _FULL_CONTAINER_ID.fullmatch(container_id):
            continue
        labels = _parse_labels(parts[2] if len(parts) > 2 else "")
        candidate = {
            "container_id": container_id,
            "policy_id": labels.get(_WORKLOAD_LABEL),
            "reason": "timeout",
        }
        if network_name := labels.get("factory.sandbox.peer_network_name"):
            candidate["network_name"] = network_name
        candidates.append(candidate)
    return candidates
