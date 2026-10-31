"""Launch orchestrator — handoff state machine for RetroArch NCI launches.

NCI is fire-and-forget (no ready-callback), so the orchestrator models
readiness explicitly via injectable probes. This is the contract the B5
spike will exercise against real hardware.
"""

from __future__ import annotations

import asyncio
from enum import Enum, auto
from typing import Callable, Awaitable

from .nci.ports import NciCommand, NciTransport


class LaunchState(Enum):
    IDLE = auto()
    LAUNCHING = auto()
    AWAITING_READY = auto()
    READY = auto()
    FAILED = auto()


# A readiness probe: returns True when the launched content is ready.
ReadinessProbe = Callable[[], Awaitable[bool]]


class LaunchOrchestrator:
    """Drives a launch sequence over any NciTransport, with injectable readiness.

    .. deprecated::
        NCI LOAD_CORE/LOAD_CONTENT launch is invalid for content launch per spike —
        use ProcessLaunchOrchestrator (process exec + VERSION readiness polling).
    """

    def __init__(
        self,
        transport: NciTransport,
        readiness_probe: ReadinessProbe,
        poll_interval: float = 0.1,
        timeout: float = 5.0,
    ) -> None:
        self._transport = transport
        self._probe = readiness_probe
        self._poll_interval = poll_interval
        self._timeout = timeout
        self.state = LaunchState.IDLE

    async def launch(self, content_path: str, core: str | None = None) -> LaunchState:
        """Execute the full launch sequence. Returns final state."""
        self.state = LaunchState.LAUNCHING

        # Build and send LOAD_CORE if specified
        if core:
            await self._transport.send_command(NciCommand("LOAD_CORE", (core,)))

        # Send LOAD_CONTENT
        await self._transport.send_command(NciCommand("LOAD_CONTENT", (content_path,)))

        # Transition to readiness polling
        self.state = LaunchState.AWAITING_READY

        elapsed = 0.0
        while elapsed < self._timeout:
            if await self._probe():
                self.state = LaunchState.READY
                return self.state
            await asyncio.sleep(self._poll_interval)
            elapsed += self._poll_interval

        self.state = LaunchState.FAILED
        return self.state

    async def quit(self) -> None:
        """Send QUIT to RetroArch."""
        await self._transport.send_command(NciCommand("QUIT"))
        self.state = LaunchState.IDLE
