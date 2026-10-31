"""Cross-process lock for atomic Docker peer alias provisioning."""
from __future__ import annotations
import os
from contextlib import contextmanager
from pathlib import Path

@contextmanager
def peer_network_provision_lock(network_name: str, lock_dir: Path):
    """Serialize peer-network check-and-attach across Sandbox processes.

    Alias inspection and Docker attachment are separate API calls. A stable
    host-local advisory lock keeps those calls atomic with respect to other
    Python Factory processes using the same Docker daemon.
    """
    import hashlib
    import stat

    lock_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory = lock_dir.lstat()
    current_uid = getattr(os, "getuid", None)
    if (not stat.S_ISDIR(directory.st_mode)
            or (current_uid is not None and directory.st_uid != current_uid())):
        raise RuntimeError("Peer-network lock directory is not a private owned directory")
    if directory.st_mode & 0o077:
        lock_dir.chmod(0o700)
    lock_name = hashlib.sha256(network_name.encode("utf-8")).hexdigest() + ".lock"
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(lock_dir / lock_name, flags, 0o600)
    acquired = False
    try:
        if os.name == "nt":
            _acquire_windows_peer_network_lock(descriptor)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_EX)
        acquired = True
        yield
    finally:
        try:
            if acquired:
                if os.name == "nt":
                    import msvcrt

                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _acquire_windows_peer_network_lock(descriptor: int) -> None:
    """Wait until the Windows byte-range lock is available.

    ``LK_LOCK`` retries only for a short, fixed interval. Provisioning can
    take longer than that, so poll the nonblocking operation until it can
    safely proceed. OS process teardown releases the byte-range lock.
    """
    import errno
    import msvcrt
    import time

    if os.fstat(descriptor).st_size == 0:
        os.write(descriptor, b"\0")
    while True:
        os.lseek(descriptor, 0, os.SEEK_SET)
        try:
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            return
        except OSError as error:
            if error.errno not in {errno.EACCES, errno.EDEADLK}:
                raise
            time.sleep(0.1)
