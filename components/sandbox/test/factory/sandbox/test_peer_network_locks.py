"""Cross-process and platform lock behavior for peer-network provisioning."""

from __future__ import annotations

import hashlib
import multiprocessing
import os
from pathlib import Path

import pytest
from factory.sandbox.runtime.adapters import docker_adapter
from factory.sandbox.runtime.adapters import docker_peer_lock


def _hold_peer_network_lock(lock_dir: str, acquired, release) -> None:
    docker_adapter._PEER_NETWORK_LOCK_DIR = Path(lock_dir)
    with docker_adapter._peer_network_provision_lock("cross-process-mesh"):
        acquired.set()
        if not release.wait(timeout=10):
            raise TimeoutError("Parent did not release the peer-network lock")

@pytest.mark.skipif(os.name == "nt", reason="POSIX flock assertion")
def test_peer_network_lock_is_held_across_processes(tmp_path) -> None:
    import fcntl

    context = multiprocessing.get_context("fork")
    acquired = context.Event()
    release = context.Event()
    lock_dir = tmp_path / "cross-process-locks"
    process = context.Process(
        target=_hold_peer_network_lock,
        args=(str(lock_dir), acquired, release),
    )
    process.start()
    descriptor = None
    try:
        assert acquired.wait(timeout=5)
        lock_name = hashlib.sha256(b"cross-process-mesh").hexdigest() + ".lock"
        descriptor = os.open(lock_dir / lock_name, os.O_CREAT | os.O_RDWR, 0o600)
        with pytest.raises(BlockingIOError):
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        release.set()
        process.join(timeout=5)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
    assert process.exitcode == 0


def test_windows_peer_lock_retries_contention_without_short_timeout(tmp_path, monkeypatch) -> None:
    import errno
    import sys
    import time as time_module
    from types import SimpleNamespace

    attempts = 0

    def locking(_descriptor: int, mode: int, length: int) -> None:
        nonlocal attempts
        assert mode == 1
        assert length == 1
        attempts += 1
        if attempts < 4:
            raise OSError(errno.EACCES, "lock is held")

    sleeps: list[float] = []
    monkeypatch.setitem(
        sys.modules, "msvcrt", SimpleNamespace(LK_NBLCK=1, locking=locking),
    )
    monkeypatch.setattr(time_module, "sleep", sleeps.append)
    lock_path = tmp_path / "windows-lock"
    with lock_path.open("w+b") as lock_file:
        docker_peer_lock._acquire_windows_peer_network_lock(lock_file.fileno())

    assert attempts == 4
    assert sleeps == [0.1, 0.1, 0.1]
