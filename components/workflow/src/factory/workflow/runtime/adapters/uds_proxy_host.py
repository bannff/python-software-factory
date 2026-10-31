"""Restrictive per-launch Unix-domain-socket ASGI proxy host."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
from pathlib import Path
import uuid
from typing import Any


@dataclass(slots=True)
class _Mounted:
    path: Path
    server: Any
    task: asyncio.Task[None]


class UvicornUDSProxyHost:
    """Run one real ASGI app per unique UDS with deterministic teardown."""

    def __init__(self, root: str | Path, *, startup_timeout: float = 10.0,
                 shutdown_timeout: float = 10.0) -> None:
        self._root = Path(root)
        self._startup_timeout = startup_timeout
        self._shutdown_timeout = shutdown_timeout
        self._mounted: dict[str, _Mounted] = {}
        self._lock = asyncio.Lock()
        self._secure_root()

    async def mount(self, app: Any, *, launch_id: str) -> str:
        del launch_id  # authority is represented by the unique generated path
        path = self._root / f"workload-{uuid.uuid4().hex}.sock"
        if len(os.fsencode(path)) >= 100:
            raise ValueError("UDS proxy path exceeds the portable 100-byte limit")
        path.unlink(missing_ok=True)
        import uvicorn
        config = uvicorn.Config(
            app, uds=str(path), lifespan="on", access_log=False,
            log_level="warning",
        )
        server = uvicorn.Server(config)
        task = asyncio.create_task(server.serve())
        try:
            await asyncio.wait_for(_wait_started(server, task), self._startup_timeout)
            if not path.is_socket():
                raise RuntimeError("UDS proxy did not create a socket")
            path.chmod(0o600)
        except Exception:
            server.should_exit = True
            await _finish(task, self._shutdown_timeout)
            path.unlink(missing_ok=True)
            raise
        endpoint = f"unix://{path}"
        async with self._lock:
            self._mounted[endpoint] = _Mounted(path, server, task)
        return endpoint

    async def unmount(self, endpoint: str) -> None:
        async with self._lock:
            mounted = self._mounted.pop(endpoint, None)
        if mounted is None:
            return
        mounted.server.should_exit = True
        try:
            await asyncio.wait_for(mounted.task, self._shutdown_timeout)
        finally:
            mounted.path.unlink(missing_ok=True)

    def _secure_root(self) -> None:
        if self._root.exists() and self._root.is_symlink():
            raise ValueError("UDS proxy root must not be a symlink")
        self._root.mkdir(parents=True, mode=0o700, exist_ok=True)
        if self._root.stat().st_uid != os.getuid():
            raise PermissionError("UDS proxy root must be owned by this process user")
        self._root.chmod(0o700)


async def _wait_started(server: Any, task: asyncio.Task[None]) -> None:
    while not server.started:
        if task.done():
            await task
            raise RuntimeError("UDS proxy exited before startup")
        await asyncio.sleep(0.01)


async def _finish(task: asyncio.Task[None], timeout: float) -> None:
    try:
        await asyncio.wait_for(task, timeout)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        task.cancel()


__all__ = ["UvicornUDSProxyHost"]
