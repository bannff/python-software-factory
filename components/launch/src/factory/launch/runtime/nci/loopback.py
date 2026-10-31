"""UDP loopback NCI listener — real-socket test double for spike/integration.

Binds a real UDP socket on 127.0.0.1, receives NCI wire bytes sent by
UdpNciTransport, records them, and can simulate a readiness signal (by
setting an asyncio Event the test/spike polls as its ReadinessProbe).

This is a TEST DOUBLE, not a product surface.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class LoopbackNciListener:
    """Receives NCI commands over a real UDP socket and records them in order."""

    host: str = "127.0.0.1"
    port: int = 0  # Ephemeral by default (OS-assigned)

    received: list[bytes] = field(default_factory=list, init=False)
    ready_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)

    _transport: asyncio.DatagramTransport | None = field(default=None, init=False)

    @property
    def bound_port(self) -> int:
        """Actual port after bind (useful when port=0 for ephemeral)."""
        if self._transport is None:
            raise RuntimeError("Listener not started")
        addr = self._transport.get_extra_info("sockname")
        return addr[1]

    async def start(self) -> int:
        """Bind and start receiving. Returns the bound port."""
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: _Protocol(self),
            local_addr=(self.host, self.port),
        )
        return self.bound_port

    async def stop(self) -> None:
        if self._transport and not self._transport.is_closing():
            self._transport.close()
            self._transport = None

    def signal_ready(self) -> None:
        """Simulate RetroArch readiness (external signal)."""
        self.ready_event.set()

    async def readiness_probe(self) -> bool:
        """ReadinessProbe-compatible: True once signal_ready() was called."""
        return self.ready_event.is_set()


class _Protocol(asyncio.DatagramProtocol):
    def __init__(self, listener: LoopbackNciListener) -> None:
        self._listener = listener

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self._listener.received.append(data)
