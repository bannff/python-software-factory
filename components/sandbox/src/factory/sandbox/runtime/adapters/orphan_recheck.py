"""Revalidate cleanup candidates under per-container advisory locks."""
from __future__ import annotations

import fcntl
import json
import os
import stat
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

_RunFn = Callable[..., tuple[int, str, str]]

_WORKLOAD_LABEL = "factory.workload"
_SECRET_EVIDENCE_HOLD_SECONDS = 600
_RECHECK_FORMAT = (
    "{{.Id}}\t{{.State.Status}}\t{{.State.FinishedAt}}\t"
    "{{.State.StartedAt}}\t{{json .Config.Labels}}"
)


def _reason_from_status(status: str) -> str:
    """Map a docker status string to the reap-reason enum."""
    return "dead" if "dead" in status.lower() else "exited"


def _age_seconds(raw_timestamp: str, now: datetime) -> float | None:
    """Reject missing, future, or unzoned Docker timestamps."""
    try:
        observed = datetime.fromisoformat(raw_timestamp.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if observed.tzinfo is None:
        return None
    age = (now - observed).total_seconds()
    return age if age >= 0 else None


def _recheck_candidate(
    run: _RunFn, candidate: dict[str, Any], now: datetime,
) -> dict[str, Any] | None:
    """Inspect authoritative state and structured labels while lock is held."""
    container_id = candidate["container_id"]
    code, output, _ = run([
        "docker", "inspect", "--format", _RECHECK_FORMAT, container_id,
    ])
    if code != 0:
        return None
    parts = output.strip().split("\t", 4)
    if len(parts) != 5 or parts[0] != container_id:
        return None
    _, state, finished_at, started_at, raw_labels = parts
    try:
        labels = json.loads(raw_labels)
    except (TypeError, ValueError):
        return None
    if not isinstance(labels, dict) or labels.get("factory.sandbox") != "true":
        return None
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in labels.items()):
        return None
    secret = labels.get("factory.sandbox.secret_output_suppressed") == "true"
    if candidate["reason"] == "timeout":
        raw_timeout = labels.get("factory.sandbox.timeout_seconds", "")
        if state != "running" or not secret or not raw_timeout.isdecimal():
            return None
        timeout_seconds = int(raw_timeout)
        age = _age_seconds(started_at, now)
        if not 60 <= timeout_seconds <= 86400 or age is None or age < timeout_seconds:
            return None
        reason = "timeout"
    else:
        if state not in {"exited", "dead"}:
            return None
        if secret:
            age = _age_seconds(finished_at, now)
            if age is None or age < _SECRET_EVIDENCE_HOLD_SECONDS:
                return None
        elif labels.get("factory.sandbox.secret_output_suppressed") not in (
            None, "false",
        ):
            return None
        reason = state
    return {
        "container_id": container_id,
        "policy_id": labels.get(_WORKLOAD_LABEL),
        "reason": reason,
        "network_name": labels.get("factory.sandbox.peer_network_name"),
    }

@contextmanager
def _collector_lock(container_id: str):
    """Hold the collector's per-container advisory lock while mutating Docker.

    A missing lock file is created but never unlinked: removing a lock file
    would allow two processes to lock different inodes for the same container.
    Any uncertain lock state prevents removal.
    """
    root = Path(os.environ.get("SANDBOX_TMP_ROOT", "/tmp/factory-sandbox"))
    directory = root / "collector-locks"
    fd = None
    acquired = False
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory_stat = directory.lstat()
        if not stat.S_ISDIR(directory_stat.st_mode) or (
            directory_stat.st_uid != os.getuid()
            or stat.S_IMODE(directory_stat.st_mode) & 0o077
        ):
            raise PermissionError("Collector lock directory is untrusted")
        fd = os.open(
            directory / f"{container_id}.lock",
            os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        file_stat = os.fstat(fd)
        if not stat.S_ISREG(file_stat.st_mode) or (
            file_stat.st_uid != os.getuid()
            or stat.S_IMODE(file_stat.st_mode) & 0o077
        ):
            raise PermissionError("Collector lock file is untrusted")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            acquired = True
    except OSError:
        pass
    try:
        yield acquired
    finally:
        if fd is not None:
            if acquired:
                fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
