"""Process-based launch orchestrator — exec + liveness + readiness polling.

Consumes ProcessLauncher + ReadinessProbe. Lifecycle:
  1. Exec via launcher -> get ProcessHandle
  2. Poll loop: check process liveness (returncode) + readiness probe
  3. Terminal states: READY (probe true + alive) or FAILED (exit/timeout)

Darwin trampoline awareness: when argv uses `open -a` (detected via
is_darwin_trampoline), the process returncode==0 is EXPECTED (the `open`
trampoline exits immediately after handing off to LaunchServices). In this
mode, readiness probe (NCI VERSION) is the SOLE success signal; returncode!=0
means the trampoline itself was rejected (e.g. app not found).
"""

from __future__ import annotations

import asyncio
from typing import Callable, Awaitable

from .orchestrator import LaunchState
from .process_launcher import ProcessLauncher, ProcessHandle
from .launch_command import is_darwin_trampoline


# Reuse the ReadinessProbe type alias from the existing orchestrator
ReadinessProbe = Callable[[], Awaitable[bool]]


class ProcessLaunchOrchestrator:
    """Drives a process-based launch with readiness polling.

    Unlike the NCI-command LaunchOrchestrator, this launches RetroArch as a
    subprocess (proven spike: retroarch -L <core> <rom> --appendconfig <cfg>)
    and polls VERSION over NCI to detect readiness.
    """

    def __init__(
        self,
        launcher: ProcessLauncher,
        readiness_probe: ReadinessProbe,
        *,
        poll_interval: float = 0.2,
        timeout: float = 10.0,
    ) -> None:
        self._launcher = launcher
        self._probe = readiness_probe
        self._poll_interval = poll_interval
        self._timeout = timeout
        self.state = LaunchState.IDLE
        self._handle: ProcessHandle | None = None
        self._failure_reason: str = ""
        self._is_trampoline: bool = False

    @property
    def failure_reason(self) -> str:
        """Human-readable failure reason (empty when not FAILED)."""
        return self._failure_reason

    async def launch(self, argv: list[str]) -> LaunchState:
        """Execute the full launch sequence. Returns final state."""
        self.state = LaunchState.LAUNCHING
        self._failure_reason = ""
        self._is_trampoline = is_darwin_trampoline(argv)

        self._handle = await self._launcher.launch(argv)

        self.state = LaunchState.AWAITING_READY

        elapsed = 0.0
        while elapsed < self._timeout:
            # Check process liveness
            if self._handle.returncode is not None:
                if self._is_trampoline:
                    # Darwin `open` trampoline: returncode==0 is expected
                    # (handoff to LaunchServices); non-zero = rejection.
                    if self._handle.returncode != 0:
                        self.state = LaunchState.FAILED
                        self._failure_reason = (
                            f"Trampoline rejected (code {self._handle.returncode})"
                            f": {self._handle.stderr_text}".rstrip()
                        )
                        return self.state
                    # returncode==0: trampoline exited normally, keep polling
                    # readiness probe (NCI VERSION) — the SOLE success signal.
                else:
                    # Linux: any exit = failure (RetroArch should stay alive)
                    self.state = LaunchState.FAILED
                    self._failure_reason = (
                        f"Process exited with code {self._handle.returncode}"
                        f": {self._handle.stderr_text}".rstrip()
                    )
                    return self.state

            # Check readiness (NCI VERSION probe)
            try:
                if await self._probe():
                    self.state = LaunchState.READY
                    return self.state
            except Exception:
                pass  # probe failure = not ready yet, keep polling

            await asyncio.sleep(self._poll_interval)
            elapsed += self._poll_interval

        # Timeout — kill the process (if still alive)
        self.state = LaunchState.FAILED
        self._failure_reason = f"Timeout after {self._timeout}s waiting for readiness"
        if self._handle and self._handle.returncode is None:
            await self._handle.terminate()
        return self.state

    async def terminate(self) -> None:
        """Terminate the launched process (if still alive)."""
        if self._handle and self._handle.returncode is None:
            await self._handle.terminate()
        self.state = LaunchState.IDLE
