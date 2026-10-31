"""Behavior tests for UdpNciTransport.query() against a real loopback UDP responder.

No mocks — a tiny asyncio UDP server stands in for RetroArch's NCI port,
so we test the actual send + recvfrom round-trip and the timeout path.
"""

from __future__ import annotations

import asyncio

import pytest

from factory.launch.runtime.nci.udp import UdpNciTransport
from factory.launch.runtime.nci.ports import NciCommand


class _FakeNciServer(asyncio.DatagramProtocol):
    """Echoes a fixed reply to any datagram — stands in for RetroArch NCI."""

    def __init__(self, reply: bytes) -> None:
        self._reply = reply
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr) -> None:
        if self.transport is not None:
            self.transport.sendto(self._reply, addr)


@pytest.mark.asyncio
async def test_query_returns_reply_from_responder():
    """query() sends the command and returns the responder's reply string."""
    loop = asyncio.get_running_loop()
    server, proto = await loop.create_datagram_endpoint(
        lambda: _FakeNciServer(b"1.22.2"), local_addr=("127.0.0.1", 0)
    )
    port = server.get_extra_info("sockname")[1]
    try:
        transport = UdpNciTransport(port=port)
        reply = await transport.query(NciCommand("VERSION"), timeout=1.0)
        assert reply == "1.22.2"
    finally:
        server.close()


@pytest.mark.asyncio
async def test_query_returns_none_on_timeout():
    """query() returns None when nothing answers within the timeout."""
    # Port with no listener -> no reply -> timeout -> None.
    transport = UdpNciTransport(port=59999)
    reply = await transport.query(NciCommand("VERSION"), timeout=0.3)
    assert reply is None
