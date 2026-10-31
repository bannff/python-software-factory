"""Safe orphan selection, revalidation, and cleanup for Sandbox containers."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Callable

from .orphan_candidates import (
    _collect_timed_out_secret,
    collect_reapable,
)
from .orphan_recheck import _age_seconds, _collector_lock, _recheck_candidate

_RunFn = Callable[..., tuple[int, str, str]]

_OWNED_NETWORK = re.compile(r"^factory-sandbox-[a-z0-9-]+$")
_EMPTY_NETWORK_GRACE_SECONDS = 120


def _remove_empty_owned_network(run: _RunFn, network_name: str) -> None:
    """Docker arbitrates a remove race after ownership and emptiness checks."""
    if not _OWNED_NETWORK.fullmatch(network_name):
        return
    code, stdout, _ = run([
        "docker", "network", "inspect", "--format",
        '{{ index .Labels "factory.sandbox.owner" }}|{{json .Containers}}',
        network_name,
    ])
    if code != 0:
        return
    owner, _, attached_json = stdout.strip().partition("|")
    try:
        attached = json.loads(attached_json)
    except (TypeError, ValueError):
        return
    if owner == "python-factory" and attached in (None, {}):
        run(["docker", "network", "rm", network_name], timeout=10)


def _retry_empty_owned_networks(run: _RunFn, now: datetime) -> None:
    """Retry cleanup of bridges orphaned by a prior transient Docker error."""
    code, stdout, _ = run([
        "docker", "network", "ls", "--filter",
        "label=factory.sandbox.owner=python-factory", "--format", "{{.Name}}",
    ])
    if code != 0:
        return
    for network_name in stdout.splitlines():
        if not _OWNED_NETWORK.fullmatch(network_name):
            continue
        code, output, _ = run([
            "docker", "network", "inspect", "--format",
            '{{ index .Labels "factory.sandbox.owner" }}|{{json .Containers}}|{{.Created}}',
            network_name,
        ])
        if code != 0:
            continue
        owner, separator, rest = output.strip().partition("|")
        attached_json, separator2, created_at = rest.rpartition("|")
        if owner != "python-factory" or not separator or not separator2:
            continue
        try:
            attached = json.loads(attached_json)
        except (TypeError, ValueError):
            continue
        age = _age_seconds(created_at, now)
        if attached not in (None, {}) or age is None or age < _EMPTY_NETWORK_GRACE_SECONDS:
            continue
        _remove_empty_owned_network(run, network_name)


def sweep_orphans(
    run: _RunFn, label: str = "factory.sandbox=true", *, now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Reap exited/dead labeled containers; return the reaped list.

    Ordering matters: collect labels+reason BEFORE ``docker rm -f`` (removal
    erases labels). Returns ``[{container_id, policy_id, reason}]`` — policy_id
    is None for unlabeled (non-workload) orphans.
    """
    reaped: list[dict[str, Any]] = []
    candidates = collect_reapable(run, label, now=now)
    candidates.extend(_collect_timed_out_secret(run, label, now=now))
    clock = now or datetime.now(timezone.utc)
    for candidate in candidates:
        with _collector_lock(candidate["container_id"]) as acquired:
            if not acquired:
                continue
            verified = _recheck_candidate(run, candidate, clock)
            if verified is None:
                continue
            code, _, _ = run(
                ["docker", "rm", "-f", candidate["container_id"]], timeout=10,
            )
            if code != 0:
                continue
            network_name = verified.get("network_name")
            if network_name:
                _remove_empty_owned_network(run, network_name)
            reaped.append({key: verified[key] for key in (
                "container_id", "policy_id", "reason",
            )})
    _retry_empty_owned_networks(run, clock)
    return reaped


__all__ = [
    "CANONICAL_PROXY_SOCKET", "build_mount_args", "collect_reapable",
    "proxy_env", "sweep_orphans", "validate_socket",
]
