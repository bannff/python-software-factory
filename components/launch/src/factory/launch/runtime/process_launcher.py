"""Process launcher seam — abstracts subprocess exec for testability.

Real impl: AsyncProcessLauncher (asyncio.create_subprocess_exec).
Fake impl: FakeProcessLauncher (records argv, configurable exit behavior).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Protocol


class ProcessHandle(Protocol):
    """Handle to a launched process. Minimal surface for liveness check + teardown."""

    @property
    def returncode(self) -> int | None:
        """None = still alive. int = exited with that code."""
        ...

    @property
    def stderr_text(self) -> str:
        """Collected stderr (best-effort, may be empty while running)."""
        ...

    async def terminate(self) -> None:
        """Request graceful termination."""
        ...


class ProcessLauncher(Protocol):
    """Protocol for launching a process from an argv list."""

    async def launch(self, argv: list[str]) -> ProcessHandle: ...


# --- Real implementation ---


class _RealProcessHandle:
    """Wraps asyncio.subprocess.Process."""

    def __init__(self, proc: asyncio.subprocess.Process) -> None:
        self._proc = proc
        self._stderr_buf: str = ""

    @property
    def returncode(self) -> int | None:
        return self._proc.returncode

    @property
    def stderr_text(self) -> str:
        return self._stderr_buf

    async def terminate(self) -> None:
        try:
            self._proc.terminate()
            await asyncio.wait_for(self._proc.wait(), timeout=3.0)
        except (ProcessLookupError, asyncio.TimeoutError):
            self._proc.kill()
        # Collect stderr after termination
        if self._proc.stderr:
            data = await self._proc.stderr.read()
            self._stderr_buf = data.decode(errors="replace")


class AsyncProcessLauncher:
    """Real process launcher using asyncio subprocess."""

    async def launch(self, argv: list[str]) -> ProcessHandle:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        return _RealProcessHandle(proc)


# --- Fake implementation (test double) ---


@dataclass
class FakeProcessHandle:
    """Configurable fake: stays alive (returncode=None) or exits immediately."""

    _returncode: int | None = None
    _stderr: str = ""

    @property
    def returncode(self) -> int | None:
        return self._returncode

    @property
    def stderr_text(self) -> str:
        return self._stderr

    async def terminate(self) -> None:
        if self._returncode is None:
            self._returncode = -15  # SIGTERM


@dataclass
class FakeProcessLauncher:
    """Test double: records argv, returns a configurable FakeProcessHandle."""

    launched_argv: list[list[str]] = field(default_factory=list)
    _exit_code: int | None = None  # None = stay alive
    _stderr: str = ""

    async def launch(self, argv: list[str]) -> ProcessHandle:
        self.launched_argv.append(list(argv))
        return FakeProcessHandle(_returncode=self._exit_code, _stderr=self._stderr)
