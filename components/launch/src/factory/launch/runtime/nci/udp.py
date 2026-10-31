"""UDP NCI transport — real network transport for RetroArch."""

from __future__ import annotations

import asyncio

from .ports import NciCommand, NciTransport, to_wire


class _ReplyProtocol(asyncio.DatagramProtocol):
    """Captures the first datagram reply into a Future."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.future: asyncio.Future[bytes] = loop.create_future()

    def datagram_received(self, data: bytes, addr) -> None:
        if not self.future.done():
            self.future.set_result(data)

    def error_received(self, exc: Exception) -> None:
        if not self.future.done():
            self.future.set_exception(exc)


class UdpNciTransport:
    """Send NCI commands over UDP. Implements NciTransport protocol."""

    def __init__(self, host: str = "127.0.0.1", port: int = 55355) -> None:
        self._host = host
        self._port = port
        self._transport: asyncio.DatagramTransport | None = None

    async def _ensure_socket(self) -> asyncio.DatagramTransport:
        if self._transport is None or self._transport.is_closing():
            loop = asyncio.get_running_loop()
            self._transport, _ = await loop.create_datagram_endpoint(
                asyncio.DatagramProtocol, remote_addr=(self._host, self._port)
            )
        return self._transport

    async def send_command(self, cmd: NciCommand) -> None:
        """Fire-and-forget: send command bytes over UDP."""
        transport = await self._ensure_socket()
        transport.sendto(to_wire(cmd))

    async def query(self, cmd: NciCommand, timeout: float = 1.0) -> str | None:
        """Send a command and await a single UDP reply. None on timeout.

        Uses a dedicated short-lived endpoint so the reply Future is scoped to
        this query (RetroArch NCI replies are one datagram per command).
        """
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: _ReplyProtocol(loop), remote_addr=(self._host, self._port)
        )
        try:
            transport.sendto(to_wire(cmd))
            try:
                data = await asyncio.wait_for(protocol.future, timeout=timeout)
            except asyncio.TimeoutError:
                return None
            except (ConnectionRefusedError, OSError):
                # No listener yet (ICMP port-unreachable) — treat as not-ready.
                return None
            return data.decode("utf-8", errors="replace").strip()
        finally:
            transport.close()

    async def close(self) -> None:
        if self._transport and not self._transport.is_closing():
            self._transport.close()
            self._transport = None


# Verify protocol conformance at import time
_: type[NciTransport] = UdpNciTransport  # type: ignore[assignment]
