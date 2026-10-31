"""VERSION readiness probe — safe alternative to GET_STATUS.

Sends NCI VERSION command via transport.query(). Returns True on any non-empty
reply (RetroArch is up and responding). Knows nothing about processes.

Why VERSION not GET_STATUS: GET_STATUS segfaults RetroArch under content load
(null strlcpy in command_get_status). VERSION is always safe.
"""

from __future__ import annotations

from .ports import NciCommand, NciTransport


class VersionProbe:
    """ReadinessProbe: queries NCI VERSION and returns True on non-empty reply."""

    def __init__(self, transport: NciTransport, timeout: float = 1.0) -> None:
        self._transport = transport
        self._timeout = timeout
        self._cmd = NciCommand("VERSION")

    async def __call__(self) -> bool:
        raw = await self._transport.query(self._cmd, timeout=self._timeout)
        return bool(raw and raw.strip())
