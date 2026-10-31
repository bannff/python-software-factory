"""GET_STATUS readiness probe — replaces the _always_ready mock.

Sends GET_STATUS over NciTransport.query(), parses the reply, reports
ready when state == PLAYING. Satisfies the ReadinessProbe callable signature.
"""

from __future__ import annotations

from .ports import NciCommand, NciTransport
from .status import NciState, parse_status


class GetStatusProbe:
    """ReadinessProbe: queries NCI GET_STATUS and returns True when PLAYING.

    # WARNING: segfaults RetroArch under content load (null strlcpy in
    # command_get_status); only valid for menu/contentless state.
    # For content-loaded readiness, use VersionProbe instead.
    """

    def __init__(self, transport: NciTransport, timeout: float = 1.0) -> None:
        self._transport = transport
        self._timeout = timeout
        self._cmd = NciCommand("GET_STATUS")

    async def __call__(self) -> bool:
        raw = await self._transport.query(self._cmd, timeout=self._timeout)
        status = parse_status(raw)
        return status.state == NciState.PLAYING
