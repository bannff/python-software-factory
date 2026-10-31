"""One supervised POSIX PTY session."""
from __future__ import annotations

import asyncio
import errno
import fcntl
import os
import pty
import signal
import struct
import sys
import termios
import time
from dataclasses import dataclass, field
from pathlib import Path

_SCROLLBACK_BYTES = 50 * 1024


def _set_size(fd: int, cols: int, rows: int) -> None:
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


@dataclass(slots=True)
class PtySession:
    session_id: str
    tenant_id: str
    principal_id: str
    shell: str
    cwd: str
    master_fd: int
    process: asyncio.subprocess.Process
    cols: int
    rows: int
    last_activity: float = field(default_factory=time.monotonic)
    disconnected_at: float | None = None
    connection_epoch: int = 0
    _cwd_probe: tuple[float, str] | None = None
    _scrollback: bytearray = field(default_factory=bytearray)
    _read_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _closed: bool = False

    @property
    def alive(self) -> bool:
        return not self._closed and self.process.returncode is None

    async def read(self, timeout: float = 0.25) -> bytes:
        """Read one available PTY chunk without leaving blocked executor threads."""
        async with self._read_lock:
            if self._closed:
                return b""
            loop = asyncio.get_running_loop()
            ready: asyncio.Future[bytes] = loop.create_future()

            def on_ready() -> None:
                try:
                    data = os.read(self.master_fd, 4096)
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        data = b""
                    else:
                        ready.set_exception(exc)
                        return
                if not ready.done():
                    ready.set_result(data)

            loop.add_reader(self.master_fd, on_ready)
            try:
                data = await asyncio.wait_for(ready, timeout=timeout)
            except TimeoutError:
                return b""
            finally:
                loop.remove_reader(self.master_fd)
            if data:
                self.last_activity = time.monotonic()
                self._scrollback.extend(data)
                del self._scrollback[:-_SCROLLBACK_BYTES]
            return data

    async def write(self, data: bytes) -> None:
        if self._closed:
            raise RuntimeError("terminal session is closed")
        await asyncio.to_thread(_write_all, self.master_fd, data)
        if b"\r" in data or b"\n" in data:
            self._cwd_probe = None
        self.last_activity = time.monotonic()

    async def current_cwd(self) -> str:
        """Return the shell process cwd without blocking the event loop."""
        now = time.monotonic()
        if self._cwd_probe is not None and now - self._cwd_probe[0] < 0.4:
            return self._cwd_probe[1]
        from .process_cwd import process_cwd
        value = await asyncio.to_thread(process_cwd, self.process.pid, self.cwd)
        self._cwd_probe = (now, value)
        return value

    def resize(self, cols: int, rows: int) -> None:
        if self._closed:
            raise RuntimeError("terminal session is closed")
        _set_size(self.master_fd, cols, rows)
        self.cols, self.rows = cols, rows
        self.last_activity = time.monotonic()

    def scrollback(self) -> bytes:
        return bytes(self._scrollback)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await asyncio.to_thread(_close_fd, self.master_fd)
        if self.process.returncode is not None:
            return
        try:
            await asyncio.wait_for(self.process.wait(), timeout=0.3)
            return
        except TimeoutError:
            pass
        for sig, wait in ((signal.SIGTERM, 0.5), (signal.SIGKILL, 0.5)):
            _signal(self.process, sig)
            try:
                await asyncio.wait_for(self.process.wait(), timeout=wait)
                return
            except TimeoutError:
                continue


def _signal(process: asyncio.subprocess.Process, sig: signal.Signals) -> None:
    try:
        os.killpg(process.pid, sig)
    except PermissionError:
        try:
            process.send_signal(sig)
        except ProcessLookupError:
            pass
    except ProcessLookupError:
        pass


def _close_fd(fd: int) -> None:
    try:
        os.close(fd)
    except OSError:
        pass


async def spawn_pty(
    session_id: str, tenant_id: str, principal_id: str, shell: str,
    cwd: str, cols: int, rows: int,
) -> PtySession:
    """Spawn the owner's login shell attached to a fresh controlling PTY."""
    working = str(Path(cwd).expanduser().resolve(strict=True))
    master_fd, slave_fd = pty.openpty()
    try:
        _set_size(slave_fd, cols, rows)
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "factory.terminal.runtime.pty_child", shell,
            stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            cwd=working, start_new_session=True,
        )
    except BaseException:
        os.close(master_fd)
        os.close(slave_fd)
        raise
    os.close(slave_fd)
    return PtySession(
        session_id, tenant_id, principal_id, shell, working, master_fd,
        process, cols, rows,
    )


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        view = view[written:]


__all__ = ["PtySession", "spawn_pty"]
